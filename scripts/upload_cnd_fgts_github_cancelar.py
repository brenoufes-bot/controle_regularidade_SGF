#!/usr/bin/env python3

from __future__ import annotations

import os
import re
import time
import traceback
from pathlib import Path
from typing import Dict, List

import fitz
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# ================= CONFIG =================

USUARIO = os.getenv("SGF_USUARIO")
SENHA = os.getenv("SGF_SENHA")

TIMEOUT = int(os.getenv("TIMEOUT", "30"))
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"

PDF_PADRAO = str(Path.cwd() / "CND_FGTS.pdf")
CAMINHO_PDF = os.getenv("CND_PDF_PATH") or os.getenv("PDF_PATH", PDF_PADRAO)

# 🔥 CORREÇÃO CRÍTICA
CAMINHO_PDF = str(Path(CAMINHO_PDF).resolve())

UFS_PADRAO = [
    uf.strip().upper()
    for uf in os.getenv("UFS_ALVO", "RJ").split(",")
    if uf.strip()
]


# ================= UTIL =================

def validar_configuracao():
    print("="*60)
    print("VALIDANDO CONFIGURAÇÃO")
    print("="*60)

    print(f"PDF: {CAMINHO_PDF}")
    print(f"HEADLESS: {HEADLESS}")

    if not USUARIO or not SENHA:
        raise RuntimeError("Usuário ou senha não configurados.")

    if not Path(CAMINHO_PDF).exists():
        raise FileNotFoundError(f"PDF não encontrado: {CAMINHO_PDF}")


def extrair_data_validade(pdf_path: str) -> str:
    print("Extraindo validade do PDF...")

    doc = fitz.open(pdf_path)
    texto = "".join(p.get_text() for p in doc)
    doc.close()

    texto = re.sub(r"\s+", " ", texto)

    m = re.search(r"(\d{2}/\d{2}/\d{4})\s*a\s*(\d{2}/\d{2}/\d{4})", texto)

    if not m:
        raise ValueError("Não encontrou validade no PDF")

    print(f"Validade encontrada: {m.group(2)}")
    return m.group(2)


def criar_driver():
    print("Criando driver...")

    opts = webdriver.ChromeOptions()

    if HEADLESS:
        opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=opts)
    return driver


def esperar(driver, by, sel):
    return WebDriverWait(driver, TIMEOUT).until(
        EC.presence_of_element_located((by, sel))
    )


def clicar(el, driver):
    try:
        el.click()
    except:
        driver.execute_script("arguments[0].click();", el)


# ================= LOGIN =================

def fazer_login(driver):
    print("Abrindo login...")

    driver.get(
        "https://amei.sebrae.com.br/auth/realms/externo/protocol/openid-connect/auth"
        "?client_id=sgf-externo&response_type=code&redirect_uri="
        "https://sgf.sebrae.com.br/Credenciado/Login.aspx"
    )

    esperar(driver, By.ID, "username").send_keys(USUARIO)
    driver.find_element(By.ID, "password").send_keys(SENHA)

    driver.find_element(By.ID, "kc-login").click()

    esperar(driver, By.ID, "lgvLogin_ddlUFContext")

    print("Login OK")


# ================= PROCESSO =================

def selecionar_uf(driver, uf):
    print(f"Selecionando UF {uf}")
    Select(driver.find_element(By.ID, "lgvLogin_ddlUFContext")).select_by_visible_text(uf)
    driver.execute_script("__doPostBack('ctl00$ctl00$lgvLogin$ddlUFContext','')")
    time.sleep(3)


def abrir_documentos(driver):
    clicar(esperar(driver, By.LINK_TEXT, "Cadastro"), driver)
    clicar(esperar(driver, By.LINK_TEXT, "Documentos Anexados"), driver)
    time.sleep(2)


def localizar_linha_fgts(driver):
    for l in driver.find_elements(By.XPATH, "//tr"):
        if "fgts" in l.text.lower():
            return l
    raise RuntimeError("Linha FGTS não encontrada")


def clicar_clipe(driver, linha):
    botoes = linha.find_elements(By.XPATH, ".//input[@type='image']")
    clicar(botoes[1], driver)


# ================= BOTÃO CANCELAR (NOVO) =================

def localizar_botao_cancelar_rodape(driver):
    print("Buscando botão Cancelar...")

    time.sleep(2)

    xpaths = [
        "//input[contains(@id,'btnCancelar')]",
        "//input[contains(@name,'btnCancelar')]",
        "//input[contains(@class,'cancelar')]",
        "//input[contains(@src,'cancelar')]",
        "//button[contains(.,'Cancelar')]",
        "//a[contains(.,'Cancelar')]",
        "//*[contains(text(),'Cancelar')]"
    ]

    for tentativa in range(3):
        for xp in xpaths:
            elementos = driver.find_elements(By.XPATH, xp)
            visiveis = [e for e in elementos if e.is_displayed()]

            if visiveis:
                print(f"Cancel encontrado via: {xp}")
                return visiveis[0]

        time.sleep(2)

    print("Fallback Cancel...")

    botoes = driver.find_elements(By.XPATH, "//input[@type='image']")
    visiveis = [b for b in botoes if b.is_displayed()]

    if visiveis:
        return visiveis[-1]

    return None


# ================= UPLOAD =================

def executar():
    validar_configuracao()

    data = extrair_data_validade(CAMINHO_PDF)

    driver = criar_driver()

    try:
        fazer_login(driver)

        for uf in UFS_PADRAO:
            selecionar_uf(driver, uf)
            abrir_documentos(driver)

            linha = localizar_linha_fgts(driver)
            clicar_clipe(driver, linha)

            time.sleep(2)

            # DATA
            campo_data = driver.find_elements(By.XPATH, "//input[@type='text']")[0]
            campo_data.clear()
            campo_data.send_keys(data)

            # PDF
            campo_file = driver.find_element(By.XPATH, "//input[@type='file']")
            campo_file.send_keys(CAMINHO_PDF)

            time.sleep(1)

            # ANEXAR
            btn = driver.find_elements(By.XPATH, "//*[contains(.,'Anexar')]")[0]
            clicar(btn, driver)

            time.sleep(2)

            # CANCELAR
            cancelar = localizar_botao_cancelar_rodape(driver)

            if not cancelar:
                raise RuntimeError("Botão cancelar não encontrado")

            clicar(cancelar, driver)

            print(f"UF {uf} OK")

        print("FINALIZADO COM SUCESSO")

    finally:
        driver.quit()


if __name__ == "__main__":
    executar()

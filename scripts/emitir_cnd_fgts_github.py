#!/usr/bin/env python3
# emitir_cnd_fgts_github.py

from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


# =========================
# CONFIGURAÇÕES
# =========================

CNPJ = os.getenv("CNPJ_EMISSAO", "06372941000132")
URL_CAIXA = "https://consulta-crf.caixa.gov.br/consultacrf/pages/consultaEmpregador.jsf"

TIMEOUT = int(os.getenv("TIMEOUT", "30"))
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"

PASTA_SALVAR = Path(os.getenv("PASTA_SALVAR", str(Path.cwd())))
NOME_ARQUIVO = os.getenv("NOME_ARQUIVO_PDF", "CND_FGTS_emitida.pdf")


# =========================
# FUNÇÕES AUXILIARES
# =========================

def esperar_elemento(wait: WebDriverWait, by: By, valor: str):
    return wait.until(EC.presence_of_element_located((by, valor)))


def esperar_clicavel(wait: WebDriverWait, by: By, valor: str):
    return wait.until(EC.element_to_be_clickable((by, valor)))


def criar_driver() -> webdriver.Chrome:
    print("=" * 70)
    print("CRIANDO DRIVER PARA EMISSÃO DA CND FGTS")
    print("=" * 70)

    PASTA_SALVAR.mkdir(parents=True, exist_ok=True)

    options = Options()

    if HEADLESS:
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
    else:
        options.add_argument("--start-maximized")

    options.add_argument("--disable-gpu")

    prefs = {
        "download.default_directory": str(PASTA_SALVAR.resolve()),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": False,
        "printing.print_preview_sticky_settings.appState": (
            '{"recentDestinations":[{"id":"Save as PDF","origin":"local","account":""}],'
            '"selectedDestinationId":"Save as PDF","version":2}'
        ),
        "savefile.default_directory": str(PASTA_SALVAR.resolve()),
    }

    options.add_experimental_option("prefs", prefs)
    options.add_argument("--kiosk-printing")

    driver = webdriver.Chrome(options=options)
    print("Driver criado com sucesso.")
    return driver


def limpar_arquivo_destino(destino_final: Path) -> None:
    if destino_final.exists():
        destino_final.unlink()


def renomear_arquivo_pdf(timeout_segundos: int = 30) -> Path | None:
    destino_final = (PASTA_SALVAR / NOME_ARQUIVO).resolve()

    limpar_arquivo_destino(destino_final)

    fim = time.time() + timeout_segundos

    while time.time() < fim:
        arquivos_pdf = list(PASTA_SALVAR.glob("*.pdf"))
        arquivos_crdownload = list(PASTA_SALVAR.glob("*.crdownload"))

        if arquivos_crdownload:
            time.sleep(1)
            continue

        candidatos = [a for a in arquivos_pdf if a.resolve() != destino_final]

        if not candidatos and destino_final.exists():
            return destino_final

        if candidatos:
            arquivo_gerado = max(candidatos, key=lambda p: p.stat().st_mtime)
            arquivo_gerado.rename(destino_final)
            return destino_final

        time.sleep(1)

    return destino_final if destino_final.exists() else None


def extrair_validade_da_pagina(driver: webdriver.Chrome) -> str:
    texto = driver.execute_script("return document.body.innerText;") or ""
    texto = re.sub(r"\s+", " ", texto)

    m = re.search(
        r"Validade\s*:?\s*\d{2}/\d{2}/\d{4}\s*a\s*(\d{2}/\d{2}/\d{4})",
        texto,
        flags=re.IGNORECASE,
    )
    if m:
        return m.group(1)

    m2 = re.search(
        r"(\d{2}/\d{2}/\d{4})\s*a\s*(\d{2}/\d{2}/\d{4})",
        texto,
        flags=re.IGNORECASE,
    )
    if m2:
        return m2.group(2)

    return ""


# =========================
# EMISSÃO
# =========================

def emitir_cnd_fgts_github(cnpj: str = CNPJ) -> dict:
    print("=" * 70)
    print("EMISSÃO CND FGTS - GITHUB")
    print("=" * 70)
    print(f"CNPJ: {cnpj}")
    print(f"PASTA_SALVAR: {PASTA_SALVAR.resolve()}")
    print(f"NOME_ARQUIVO: {NOME_ARQUIVO}")
    print(f"HEADLESS: {HEADLESS}")
    print(f"TIMEOUT: {TIMEOUT}")

    driver = criar_driver()
    wait = WebDriverWait(driver, TIMEOUT)

    try:
        print("1) Abrindo site da Caixa...")
        driver.get(URL_CAIXA)

        print("2) Preenchendo CNPJ...")
        campo = esperar_elemento(wait, By.ID, "mainForm:txtInscricao1")
        campo.clear()
        campo.send_keys(cnpj)

        print("3) Clicando em Consultar...")
        esperar_clicavel(wait, By.ID, "mainForm:btnConsultar").click()

        print("4) Clicando no link do CRF...")
        esperar_clicavel(wait, By.ID, "mainForm:j_id51").click()

        print("5) Capturando validade final...")
        validade = extrair_validade_da_pagina(driver)
        print(f"   Validade final: {validade}")

        print("6) Clicando em Visualizar...")
        esperar_clicavel(wait, By.XPATH, "//input[@value='Visualizar']").click()

        print("7) Aguardando tela antes de imprimir...")
        esperar_clicavel(wait, By.XPATH, "//input[@value='Imprimir']")

        print("8) Clicando em Imprimir...")
        esperar_clicavel(wait, By.XPATH, "//input[@value='Imprimir']").click()

        time.sleep(5)

        print("9) Aguardando PDF ser salvo...")
        arquivo_final = renomear_arquivo_pdf(timeout_segundos=40)

        if arquivo_final and arquivo_final.exists():
            print(f"PDF salvo com sucesso em:\n{arquivo_final}")
            sucesso = True
        else:
            print("Não encontrei o PDF salvo automaticamente.")
            sucesso = False

        return {
            "validade_final": validade,
            "arquivo_pdf": str(arquivo_final.resolve()) if arquivo_final and arquivo_final.exists() else "",
            "sucesso": sucesso,
        }

    except TimeoutException as e:
        print("\nTimeout: algum elemento esperado não apareceu a tempo.")
        print(f"Detalhe técnico: {e}")
        raise

    except Exception as e:
        print("\nErro inesperado durante a automação.")
        print(f"Detalhe técnico: {e}")
        raise

    finally:
        try:
            driver.quit()
            print("Driver encerrado com sucesso.")
        except Exception:
            pass


def main():
    try:
        resultado = emitir_cnd_fgts_github()
        print("\nRESULTADO FINAL:")
        print(resultado)

        if not resultado.get("sucesso"):
            sys.exit(1)

    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    main()

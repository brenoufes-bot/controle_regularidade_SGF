#!/usr/bin/env python3
# V6.4 - mínima alteração sobre a V6.3
# Mantém a lógica da V6.1/V6.2
# Remove USUARIO e SENHA do código
# Lê automaticamente do arquivo: controle_regularidade_SGF_email.env
# Mantém o JSON_PATH fixo igual ao da V6.1
# Grava datas no Google Sheets como USER_ENTERED para virar data real
# Mantém input final para o prompt não fechar

from __future__ import annotations

import time
import re
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
import os

import gspread
from google.oauth2.service_account import Credentials

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC


# Carrega o arquivo .env da mesma pasta do script
PASTA_SCRIPT = Path(__file__).resolve().parent
ARQUIVO_ENV = PASTA_SCRIPT / "controle_regularidade_SGF_email.env"

if ARQUIVO_ENV.exists():
    load_dotenv(dotenv_path=ARQUIVO_ENV)

USUARIO = os.getenv("SGF_USUARIO")
SENHA = os.getenv("SGF_SENHA")

UFS_ALVO = ["RJ", "SP", "TO"]

DOC_FEDERAL = "Fazenda Federal"
DOC_MUNICIPAL = "Fazenda Municipal"
DOC_FGTS = "FGTS"

SPREADSHEET_ID = "1yto0gUfVPmYZx4c_CycvlsB48ZpHJT4wMepaJqhCTQs"
ABA = "Validade CNDs"

# Mantido igual à V6.1
JSON_PATH = r"C:\Users\breno\OneDrive\Gestao Financeira SPM\CNDs\FGTS\google_sheets_cred.json"


def criar_driver():
    opts = webdriver.ChromeOptions()
    opts.add_argument("--start-maximized")
    return webdriver.Chrome(options=opts)


def esperar(driver, by, sel, t=30):
    return WebDriverWait(driver, t).until(
        EC.presence_of_element_located((by, sel))
    )


def validar_configuracao():
    faltando = []

    if not ARQUIVO_ENV.exists():
        faltando.append(f"arquivo .env não encontrado: {ARQUIVO_ENV}")

    if not USUARIO:
        faltando.append("SGF_USUARIO no arquivo controle_regularidade_SGF_email.env")

    if not SENHA:
        faltando.append("SGF_SENHA no arquivo controle_regularidade_SGF_email.env")

    if faltando:
        raise RuntimeError("Configuração ausente:\n- " + "\n- ".join(faltando))


def fazer_login(driver):

    url = (
        "https://amei.sebrae.com.br/auth/realms/externo/protocol/openid-connect/auth"
        "?client_id=sgf-externo&response_type=code&redirect_uri="
        "https://sgf.sebrae.com.br/Credenciado/Login.aspx"
    )

    driver.get(url)

    esperar(driver, By.ID, "username").send_keys(USUARIO)
    driver.find_element(By.ID, "password").send_keys(SENHA)
    driver.find_element(By.ID, "kc-login").click()

    esperar(driver, By.ID, "lgvLogin_ddlUFContext")


def selecionar_uf(driver, uf):

    Select(
        driver.find_element(By.ID, "lgvLogin_ddlUFContext")
    ).select_by_visible_text(uf)

    driver.execute_script(
        "__doPostBack('ctl00$ctl00$lgvLogin$ddlUFContext','')"
    )

    time.sleep(3)


def abrir_documentos(driver):

    driver.find_element(By.LINK_TEXT, "Cadastro").click()
    time.sleep(1)

    driver.find_element(
        By.LINK_TEXT, "Documentos Anexados"
    ).click()

    time.sleep(2)


def ler_datas(driver):

    dados = {
        DOC_FEDERAL: "",
        DOC_MUNICIPAL: "",
        DOC_FGTS: "",
    }

    linhas = driver.find_elements(By.TAG_NAME, "tr")

    for l in linhas:

        txt = l.text.lower()

        if "federal" in txt:
            m = re.search(r"\d{2}/\d{2}/\d{4}", txt)
            if m:
                dados[DOC_FEDERAL] = m.group(0)

        if "municipal" in txt:
            m = re.search(r"\d{2}/\d{2}/\d{4}", txt)
            if m:
                dados[DOC_MUNICIPAL] = m.group(0)

        if "fgts" in txt:
            m = re.search(r"\d{2}/\d{2}/\d{4}", txt)
            if m:
                dados[DOC_FGTS] = m.group(0)

    return dados


def gravar_google(dados):

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets"
    ]

    creds = Credentials.from_service_account_file(
        JSON_PATH,
        scopes=scopes,
    )

    client = gspread.authorize(creds)

    ws = client.open_by_key(
        SPREADSHEET_ID
    ).worksheet(ABA)

    agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    ws.update(range_name="B5", values=[[agora]])

    # USER_ENTERED faz o Sheets interpretar as strings como data
    ws.update(range_name="C8", values=[[dados["RJ"][DOC_FEDERAL]]], value_input_option="USER_ENTERED")
    ws.update(range_name="E8", values=[[dados["SP"][DOC_FEDERAL]]], value_input_option="USER_ENTERED")
    ws.update(range_name="G8", values=[[dados["TO"][DOC_FEDERAL]]], value_input_option="USER_ENTERED")

    ws.update(range_name="C9", values=[[dados["RJ"][DOC_MUNICIPAL]]], value_input_option="USER_ENTERED")
    ws.update(range_name="E9", values=[[dados["SP"][DOC_MUNICIPAL]]], value_input_option="USER_ENTERED")
    ws.update(range_name="G9", values=[[dados["TO"][DOC_MUNICIPAL]]], value_input_option="USER_ENTERED")

    ws.update(range_name="C10", values=[[dados["RJ"][DOC_FGTS]]], value_input_option="USER_ENTERED")
    ws.update(range_name="E10", values=[[dados["SP"][DOC_FGTS]]], value_input_option="USER_ENTERED")
    ws.update(range_name="G10", values=[[dados["TO"][DOC_FGTS]]], value_input_option="USER_ENTERED")

    # Garante formato de data no intervalo das validades
    ws.format("C8:G10", {
        "numberFormat": {
            "type": "DATE",
            "pattern": "dd/MM/yyyy"
        }
    })


def main():

    driver = None

    try:
        print("Validando configuração...")
        validar_configuracao()

        print("Abrindo navegador...")
        driver = criar_driver()

        print("Fazendo login...")
        fazer_login(driver)

        dados = {}

        for uf in UFS_ALVO:

            print(f"Lendo documentos da UF {uf}...")
            selecionar_uf(driver, uf)
            abrir_documentos(driver)
            dados[uf] = ler_datas(driver)

        print("Gravando na planilha...")
        gravar_google(dados)

        print("Concluído com sucesso.")

    except Exception as e:
        print("\nERRO NA EXECUÇÃO:")
        print(str(e))

    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

        input("\nPressione Enter para fechar...")


if __name__ == "__main__":
    main()

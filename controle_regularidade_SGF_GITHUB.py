# controle_regularidade_SGF_GITHUB.py
# versão para GitHub (sem .env)

import json
import os
import re
import time
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

USUARIO = os.getenv("SGF_USUARIO")
SENHA = os.getenv("SGF_SENHA")
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")

UFS_ALVO = ["RJ", "SP", "TO"]

DOC_FEDERAL = "Fazenda Federal"
DOC_MUNICIPAL = "Fazenda Municipal"
DOC_FGTS = "FGTS"

SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
ABA = "Validade CNDs"

def criar_driver():
    opts = webdriver.ChromeOptions()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(options=opts)

def esperar(driver, by, sel, t=30):
    return WebDriverWait(driver, t).until(
        EC.presence_of_element_located((by, sel))
    )

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
    Select(driver.find_element(By.ID, "lgvLogin_ddlUFContext")).select_by_visible_text(uf)
    driver.execute_script("__doPostBack('ctl00$ctl00$lgvLogin$ddlUFContext','')")
    time.sleep(3)

def abrir_documentos(driver):
    driver.find_element(By.LINK_TEXT, "Cadastro").click()
    time.sleep(1)
    driver.find_element(By.LINK_TEXT, "Documentos Anexados").click()
    time.sleep(2)

def ler_datas(driver):
    dados = {DOC_FEDERAL: "", DOC_MUNICIPAL: "", DOC_FGTS: ""}
    linhas = driver.find_elements(By.TAG_NAME, "tr")
    for linha in linhas:
        txt = linha.text.lower()
        for chave in dados:
            if chave.lower() in txt:
                m = re.search(r"\d{2}/\d{2}/\d{4}", txt)
                if m:
                    dados[chave] = m.group(0)
    return dados

def gravar_google(dados):
    creds = Credentials.from_service_account_info(
        json.loads(GOOGLE_SERVICE_ACCOUNT_JSON),
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    client = gspread.authorize(creds)
    ws = client.open_by_key(SPREADSHEET_ID).worksheet(ABA)

    agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    ws.update("B5", [[agora]])

    ws.update("C8", [[dados["RJ"][DOC_FEDERAL]]], value_input_option="USER_ENTERED")
    ws.update("E8", [[dados["SP"][DOC_FEDERAL]]], value_input_option="USER_ENTERED")
    ws.update("G8", [[dados["TO"][DOC_FEDERAL]]], value_input_option="USER_ENTERED")

    ws.update("C9", [[dados["RJ"][DOC_MUNICIPAL]]], value_input_option="USER_ENTERED")
    ws.update("E9", [[dados["SP"][DOC_MUNICIPAL]]], value_input_option="USER_ENTERED")
    ws.update("G9", [[dados["TO"][DOC_MUNICIPAL]]], value_input_option="USER_ENTERED")

    ws.update("C10", [[dados["RJ"][DOC_FGTS]]], value_input_option="USER_ENTERED")
    ws.update("E10", [[dados["SP"][DOC_FGTS]]], value_input_option="USER_ENTERED")
    ws.update("G10", [[dados["TO"][DOC_FGTS]]], value_input_option="USER_ENTERED")

def main():
    driver = criar_driver()
    fazer_login(driver)

    dados = {}
    for uf in UFS_ALVO:
        selecionar_uf(driver, uf)
        abrir_documentos(driver)
        dados[uf] = ler_datas(driver)

    gravar_google(dados)
    driver.quit()

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# upload_cnd_fgts_github_cancelar.py
#
# Versão adaptada para GitHub Actions:
# - sem caminho fixo Windows
# - sem .env obrigatório
# - sem input/pause
# - usa Secrets / variáveis de ambiente
# - mantém a lógica de TESTE: anexa e clica em Cancelar
#
# Variáveis esperadas:
#   SGF_USUARIO
#   SGF_SENHA
# Opcionais:
#   CND_PDF_PATH / PDF_PATH  -> caminho do PDF (default: ./CND_FGTS.pdf)
#   HEADLESS                 -> true/false (default: true)
#   UFS_ALVO                 -> ex: RJ,TO,SP  (default: RJ,TO,SP)
#   TIMEOUT                  -> default: 30

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


USUARIO = os.getenv("SGF_USUARIO")
SENHA = os.getenv("SGF_SENHA")

TIMEOUT = int(os.getenv("TIMEOUT", "30"))
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"

PDF_PADRAO = str(Path.cwd() / "CND_FGTS.pdf")

CAMINHO_PDF = os.getenv("CND_PDF_PATH") or os.getenv("PDF_PATH", PDF_PADRAO)

# 🔥 CONVERSÃO PARA CAMINHO ABSOLUTO (ESSENCIAL PARA SELENIUM)
CAMINHO_PDF = str(Path(CAMINHO_PDF).resolve())

UFS_PADRAO = [
    uf.strip().upper()
    for uf in os.getenv("UFS_ALVO", "RJ,TO,SP").split(",")
    if uf.strip()
]


def validar_configuracao() -> None:
    print("=" * 70)
    print("VALIDANDO CONFIGURAÇÕES")
    print("=" * 70)
    print(f"Diretório atual: {Path.cwd()}")
    print(f"HEADLESS: {HEADLESS}")
    print(f"TIMEOUT: {TIMEOUT}")
    print(f"PDF configurado: {CAMINHO_PDF}")
    print(f"UFs alvo: {UFS_PADRAO}")

    faltando = []

    if not USUARIO:
        faltando.append("SGF_USUARIO")
    if not SENHA:
        faltando.append("SGF_SENHA")

    if faltando:
        raise RuntimeError(
            "Variáveis obrigatórias ausentes:\n- " + "\n- ".join(faltando)
        )

    if not Path(CAMINHO_PDF).exists():
        raise FileNotFoundError(f"PDF não encontrado em:\n{CAMINHO_PDF}")

    print("Configuração validada com sucesso.")


def extrair_data_validade(pdf_path: str) -> str:
    print("=" * 70)
    print("EXTRAINDO DATA DE VALIDADE DO PDF")
    print("=" * 70)
    print(f"Lendo PDF: {pdf_path}")

    doc = fitz.open(pdf_path)
    try:
        texto = "".join(p.get_text() for p in doc)
    finally:
        doc.close()

    texto_limpo = re.sub(r"\s+", " ", texto)

    m = re.search(
        r"Validade\s*:?\s*(\d{2}/\d{2}/\d{4})\s*a\s*(\d{2}/\d{2}/\d{4})",
        texto_limpo,
        flags=re.IGNORECASE,
    )
    if m:
        print(f"Validade localizada no PDF: {m.group(1)} a {m.group(2)}")
        return m.group(2)

    m2 = re.search(
        r"(\d{2}/\d{2}/\d{4})\s*a\s*(\d{2}/\d{2}/\d{4})",
        texto_limpo,
        flags=re.IGNORECASE,
    )
    if m2:
        print(f"Faixa de datas localizada no PDF: {m2.group(1)} a {m2.group(2)}")
        return m2.group(2)

    raise ValueError("Não foi possível localizar a data final de validade dentro do PDF.")


def criar_driver() -> webdriver.Chrome:
    print("=" * 70)
    print("CRIANDO DRIVER CHROME")
    print("=" * 70)

    opts = webdriver.ChromeOptions()

    if HEADLESS:
        opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--window-size=1920,1080")
    else:
        opts.add_argument("--start-maximized")

    opts.add_argument("--disable-gpu")

    driver = webdriver.Chrome(options=opts)
    print("Driver Chrome criado com sucesso.")
    return driver


def esperar(driver: webdriver.Chrome, by: By, seletor: str, timeout: int = TIMEOUT):
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((by, seletor))
    )


def esperar_clicavel(driver: webdriver.Chrome, by: By, seletor: str, timeout: int = TIMEOUT):
    return WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((by, seletor))
    )


def clicar_elemento(driver: webdriver.Chrome, elemento) -> None:
    try:
        elemento.click()
        return
    except Exception:
        pass

    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", elemento)
        time.sleep(0.3)
        elemento.click()
        return
    except Exception:
        pass

    driver.execute_script("arguments[0].click();", elemento)


def esperar_e_clicar(driver: webdriver.Chrome, by: By, seletor: str, timeout: int = TIMEOUT) -> None:
    el = esperar_clicavel(driver, by, seletor, timeout)
    clicar_elemento(driver, el)


def fazer_login(driver: webdriver.Chrome) -> None:
    login_url = (
        "https://amei.sebrae.com.br/auth/realms/externo/protocol/openid-connect/auth"
        "?client_id=sgf-externo&response_type=code&redirect_uri="
        "https://sgf.sebrae.com.br/Credenciado/Login.aspx"
    )

    print("=" * 70)
    print("LOGIN NO SGF")
    print("=" * 70)
    print("Abrindo página de login...")
    driver.get(login_url)

    print("Preenchendo usuário...")
    esperar(driver, By.ID, "username").send_keys(USUARIO)

    print("Preenchendo senha...")
    driver.find_element(By.ID, "password").send_keys(SENHA)

    print("Clicando em entrar...")
    driver.find_element(By.ID, "kc-login").click()

    print("Aguardando combo de UF...")
    esperar(driver, By.ID, "lgvLogin_ddlUFContext")
    print("Login concluído com sucesso.")


def selecionar_uf(driver: webdriver.Chrome, uf: str) -> None:
    print(f"Selecionando UF {uf}...")
    Select(driver.find_element(By.ID, "lgvLogin_ddlUFContext")).select_by_visible_text(uf)
    driver.execute_script("__doPostBack('ctl00$ctl00$lgvLogin$ddlUFContext','')")
    time.sleep(3)


def abrir_documentos_anexados(driver: webdriver.Chrome) -> None:
    print("Acessando menu Cadastro...")
    esperar_e_clicar(driver, By.LINK_TEXT, "Cadastro")
    time.sleep(1)

    print("Acessando Documentos Anexados...")
    esperar_e_clicar(driver, By.LINK_TEXT, "Documentos Anexados")
    time.sleep(2)


def localizar_linha_fgts(driver: webdriver.Chrome):
    print("Localizando a linha do FGTS...")
    linhas = driver.find_elements(By.XPATH, "//tr")
    for linha in linhas:
        try:
            texto_linha = linha.text.lower()
            if "fgts" in texto_linha and "comprovante de regularidade" in texto_linha:
                print("Linha do FGTS localizada.")
                return linha
        except Exception:
            pass
    raise RuntimeError("Não encontrei a linha do documento de FGTS na tabela.")


def clicar_clipe_da_linha_fgts(driver: webdriver.Chrome, linha_fgts) -> None:
    print("Procurando os ícones da linha do FGTS...")
    botoes_imagem = linha_fgts.find_elements(By.XPATH, ".//input[@type='image']")

    if len(botoes_imagem) < 2:
        raise RuntimeError(f"Esperava pelo menos 2 ícones na linha do FGTS, mas encontrei {len(botoes_imagem)}.")

    print(f"Ícones encontrados na linha do FGTS: {len(botoes_imagem)}")
    print("Clicando especificamente no SEGUNDO ícone (clipe / anexar)...")
    clicar_elemento(driver, botoes_imagem[1])


def localizar_modal_anexo(driver: webdriver.Chrome):
    print("Aguardando janela de anexação...")
    WebDriverWait(driver, TIMEOUT).until(
        EC.presence_of_element_located((By.XPATH, "//*[contains(normalize-space(.), 'Anexar Documento')]"))
    )

    candidatos = driver.find_elements(By.XPATH, "//*[contains(normalize-space(.), 'Anexar Documento')]")
    for c in candidatos:
        try:
            if c.is_displayed():
                print("Janela de anexação localizada.")
                return c
        except Exception:
            pass

    raise RuntimeError("A janela de anexação apareceu visualmente, mas não consegui localizar o título.")


def obter_contexto_modal(titulo_modal):
    xpaths = [
        "./ancestor::div[1]",
        "./ancestor::table[1]",
        "./ancestor::*[self::div or self::table][1]",
        "./..",
    ]
    for xp in xpaths:
        try:
            res = titulo_modal.find_elements(By.XPATH, xp)
            if res:
                return res[0]
        except Exception:
            pass
    return titulo_modal


def localizar_campo_data(driver: webdriver.Chrome, contexto):
    campos_texto = []
    try:
        campos_texto = contexto.find_elements(By.XPATH, ".//input[not(@type) or @type='text']")
        campos_texto = [c for c in campos_texto if c.is_displayed()]
    except Exception:
        pass

    if not campos_texto:
        campos_texto = driver.find_elements(By.XPATH, "//input[not(@type) or @type='text']")
        campos_texto = [c for c in campos_texto if c.is_displayed()]

    if not campos_texto:
        raise RuntimeError("Não encontrei o campo de data de validade na janela.")

    print("Campo de data localizado.")
    return campos_texto[0]


def localizar_campo_arquivo(driver: webdriver.Chrome, contexto):
    campos_arquivo = []
    try:
        campos_arquivo = contexto.find_elements(By.XPATH, ".//input[@type='file']")
        campos_arquivo = [c for c in campos_arquivo if c.is_displayed()]
    except Exception:
        pass

    if not campos_arquivo:
        campos_arquivo = driver.find_elements(By.XPATH, "//input[@type='file']")
        campos_arquivo = [c for c in campos_arquivo if c.is_displayed()]

    if not campos_arquivo:
        raise RuntimeError("Não encontrei o campo de seleção de arquivo na janela.")

    print("Campo de arquivo localizado.")
    return campos_arquivo[0]


def localizar_botao_anexar(driver: webdriver.Chrome, contexto):
    candidatos_xpath = [
        ".//*[self::input or self::button or self::a or self::span][@value='Anexar']",
        ".//*[self::input or self::button or self::a or self::span][contains(@id,'btnAnexar')]",
        ".//*[self::input or self::button or self::a or self::span][contains(normalize-space(.), 'Anexar')]",
        ".//*[contains(@onclick,'Anexar')]",
    ]

    for xp in candidatos_xpath:
        try:
            elementos = contexto.find_elements(By.XPATH, xp)
            visiveis = [e for e in elementos if e.is_displayed()]
            if visiveis:
                print(f"Botão Anexar localizado no contexto com XPath: {xp}")
                return visiveis[0]
        except Exception:
            pass

    candidatos_xpath_global = [
        "//*[self::input or self::button or self::a or self::span][@value='Anexar']",
        "//*[self::input or self::button or self::a or self::span][contains(@id,'btnAnexar')]",
        "//*[self::input or self::button or self::a or self::span][contains(normalize-space(.), 'Anexar')]",
        "//*[contains(@onclick,'Anexar')]",
    ]

    for xp in candidatos_xpath_global:
        try:
            elementos = driver.find_elements(By.XPATH, xp)
            visiveis = [e for e in elementos if e.is_displayed()]
            if visiveis:
                print(f"Botão Anexar localizado globalmente com XPath: {xp}")
                return visiveis[0]
        except Exception:
            pass

    return None


def localizar_botao_cancelar_rodape(driver: webdriver.Chrome):
    print("Localizando botão Cancelar no rodapé pelo seletor técnico...")

    xpaths = [
        "//input[@type='image' and contains(@id,'cucDocumentosAnexados') and contains(@id,'btnCancelar')]",
        "//input[@type='image' and contains(@name,'cucDocumentosAnexados') and contains(@name,'btnCancelar')]",
        "//input[@type='image' and contains(@class,'cancelarButton')]",
        "//input[@type='image' and contains(@onclick,'btnCancelar')]",
        "//input[@type='image' and contains(@src,'cancelar')]",
    ]

    for xp in xpaths:
        try:
            elementos = driver.find_elements(By.XPATH, xp)
            visiveis = [e for e in elementos if e.is_displayed()]
            if visiveis:
                print(f"Botão Cancelar encontrado com XPath: {xp}")
                return visiveis[0]
        except Exception:
            pass

    return None


def preencher_data_com_confirmacao(driver: webdriver.Chrome, campo_data, data_esperada: str) -> str:
    print(f"Preenchendo data de validade por JavaScript: {data_esperada}")

    driver.execute_script(
        """
        const el = arguments[0];
        const valor = arguments[1];

        el.focus();
        el.value = '';
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));

        el.value = valor;
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
        el.blur();
        """,
        campo_data,
        data_esperada,
    )

    time.sleep(1)

    valor_lido = (campo_data.get_attribute("value") or "").strip()
    print(f"Valor lido após JS: {valor_lido}")

    if valor_lido == data_esperada:
        return valor_lido

    print("JS não confirmou a data corretamente. Tentando reforço com teclado...")
    clicar_elemento(driver, campo_data)
    time.sleep(0.3)
    campo_data.send_keys(Keys.CONTROL, "a")
    time.sleep(0.2)
    campo_data.send_keys(Keys.DELETE)
    time.sleep(0.2)
    campo_data.send_keys(data_esperada)
    time.sleep(0.3)
    campo_data.send_keys(Keys.TAB)
    time.sleep(1)

    valor_lido = (campo_data.get_attribute("value") or "").strip()
    print(f"Valor lido após reforço com teclado: {valor_lido}")

    if valor_lido != data_esperada:
        raise RuntimeError(f"Data não confirmada no campo. Esperado: {data_esperada} | Lido: {valor_lido}")

    return valor_lido


def preencher_modal_anexo(driver: webdriver.Chrome, data_validade: str, caminho_pdf: str) -> Dict[str, str]:
    titulo_modal = localizar_modal_anexo(driver)
    contexto = obter_contexto_modal(titulo_modal)

    campo_data = localizar_campo_data(driver, contexto)
    valor_confirmado = preencher_data_com_confirmacao(driver, campo_data, data_validade)

    print("Selecionando arquivo PDF...")
    campo_arquivo = localizar_campo_arquivo(driver, contexto)
    campo_arquivo.send_keys(caminho_pdf)
    time.sleep(1)

    print("Localizando botão Anexar...")
    botao_anexar = localizar_botao_anexar(driver, contexto)
    if botao_anexar is None:
        raise RuntimeError("Não encontrei o botão Anexar na janela.")

    print(f"Data confirmada antes do clique em Anexar: {valor_confirmado}")
    print("Clicando em Anexar...")
    clicar_elemento(driver, botao_anexar)
    time.sleep(2)

    return {
        "data_validade_confirmada": valor_confirmado,
        "arquivo_pdf": caminho_pdf,
    }


def rotina_uf_cancelar(driver: webdriver.Chrome, uf: str, data_validade: str, caminho_pdf: str) -> Dict[str, str]:
    print("\n" + "=" * 70)
    print(f"INICIANDO ROTINA DA UF: {uf}")
    print("=" * 70)

    selecionar_uf(driver, uf)
    abrir_documentos_anexados(driver)

    linha_fgts = localizar_linha_fgts(driver)
    clicar_clipe_da_linha_fgts(driver, linha_fgts)
    time.sleep(1)

    resultado_modal = preencher_modal_anexo(driver, data_validade, caminho_pdf)

    botao_cancelar = localizar_botao_cancelar_rodape(driver)
    if botao_cancelar is None:
        raise RuntimeError(f"Não encontrei o botão Cancelar após anexar na UF {uf}.")

    print(f"Clicando em Cancelar para a UF {uf}...")
    clicar_elemento(driver, botao_cancelar)
    time.sleep(2)
    print(f"Rotina da UF {uf} concluída com Cancelar.")

    resultado_modal["uf"] = uf
    resultado_modal["acao_final"] = "cancelar"
    return resultado_modal


def upload_cnd_fgts_github_cancelar(
    *,
    caminho_pdf: str = CAMINHO_PDF,
    ufs: List[str] | None = None,
) -> List[Dict[str, str]]:
    if ufs is None:
        ufs = UFS_PADRAO.copy()

    print("=" * 70)
    print("UPLOAD CND FGTS - GITHUB - MODO CANCELAR")
    print("=" * 70)
    print(f"PDF localizado: {caminho_pdf}")

    data_validade = extrair_data_validade(caminho_pdf)
    print(f"Data FINAL de validade usada no SGF: {data_validade}")

    driver = None
    resultados: List[Dict[str, str]] = []

    try:
        driver = criar_driver()
        fazer_login(driver)

        for uf in ufs:
            resultado = rotina_uf_cancelar(driver, uf, data_validade, caminho_pdf)
            resultados.append(resultado)

        print("\nOK. Rotinas concluídas com Cancelar.")
        return resultados

    except Exception as e:
        print("\nERRO NA EXECUÇÃO:")
        print(str(e))
        print("\nDETALHES TÉCNICOS:")
        traceback.print_exc()
        raise

    finally:
        if driver is not None:
            try:
                driver.quit()
                print("Driver encerrado com sucesso.")
            except Exception:
                pass


def main() -> None:
    validar_configuracao()
    resultados = upload_cnd_fgts_github_cancelar()
    print("\nRESULTADOS:")
    print(resultados)


if __name__ == "__main__":
    main()

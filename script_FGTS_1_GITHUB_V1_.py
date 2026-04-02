# SCRIPT_FGTS_1_GITHUB_V1_.py
# Verifica a planilha no GitHub Actions e informa se deve emitir no PC local

from __future__ import annotations

import json
import os
import sys

import gspread
from google.oauth2.service_account import Credentials


def fail(msg: str) -> None:
    print(f"ERRO: {msg}")
    sys.exit(1)


def get_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        fail(f"Variável de ambiente obrigatória não informada: {name}")
    return value


def escrever_output(nome: str, valor: str) -> None:
    github_output = os.getenv("GITHUB_OUTPUT", "").strip()
    if not github_output:
        print(f"{nome}={valor}")
        return

    with open(github_output, "a", encoding="utf-8") as f:
        f.write(f"{nome}={valor}\n")


def conectar_planilha():
    json_raw = get_env("GOOGLE_SERVICE_ACCOUNT_JSON")
    spreadsheet_id = get_env("SPREADSHEET_ID")
    aba_planilha = get_env("ABA_PLANILHA")

    try:
        info = json.loads(json_raw)
    except json.JSONDecodeError as e:
        fail(f"GOOGLE_SERVICE_ACCOUNT_JSON inválido: {e}")

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    creds = Credentials.from_service_account_info(info, scopes=scopes)
    gc = gspread.authorize(creds)
    planilha = gc.open_by_key(spreadsheet_id)
    return planilha.worksheet(aba_planilha)


def main() -> None:
    celula_status = get_env("CELULA_STATUS")
    status_disparo = get_env("STATUS_DISPARO").upper()

    aba = conectar_planilha()
    valor_lido = (aba.acell(celula_status).value or "").strip().upper()

    print(f"Valor encontrado em {celula_status}: {valor_lido}")

    emitir = "true" if valor_lido == status_disparo else "false"

    escrever_output("emitir", emitir)
    escrever_output("valor_lido", valor_lido)

    print(f"Resultado final: emitir={emitir}")


if __name__ == "__main__":
    main()

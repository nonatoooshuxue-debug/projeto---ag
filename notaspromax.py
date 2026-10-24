import pandas as pd
from openpyxl import load_workbook
import streamlit as st
import numpy as np
import io


st.set_page_config(layout="wide")


colunas = [
  "FILIAL",
  "OPERACAO .",
  "DT. OPERACAO",
  "EMISSAO",
  "NOTA",
  "CLIENTE",
  "NOME",
  "PRODUTO",
  "UNIDADE",
  "DESCRIÇÃO",
  "QTDE",
  "VALOR",
]


MAP_MATERIAL = {
    104195: 38632,  # PALETE MADEIRA 1,00 M
    37108: 38736,   # CHAPATEX
    42069: 38737,   # PALETE MADEIRA 1,05 M (PBR2)
    198214: 38784,  # GFA VIDRO 330ML ÂMBAR
    786238: 38911,  # GARRAFA VERDE         <- conferir
    863059: 39891,  # GARRAFEIRA PRETA      <- conferir
    899599: 40749,  # GARRAFEIRA 24 G 600ML <- conferir
    188005: 38781,  # GARRAFEIRA 12 G 1L    <- conferir
    188006: 38782,  # GFA VIDRO 1L
}

MAP_FABRICA = {
    "FAB. AQUIRAZ": "F. Aquiraz",
    "F. AQUIRAZ": "F. Aquiraz",
    "AMBEV - F. AQUIRAZ": "F. Aquiraz",
    "F. TERESINA": "F. Teresina",
    "FILIAL TERESINA": "F. Teresina",
    "F. PERNAMBUCO": "F. Pernambuco",
    "F. A. CLARAS": "F. A. Claras",
}

SINAL = 1


st.title("PRODUTOS AG - BALANÇO NOTAS DE ENTRADA E SAIDA (PROMAX E AMBEV)")

arquivos_1 = st.sidebar.file_uploader("Coloque suas notas do promax:", type=["csv", "xlsx"], accept_multiple_files=True, key="uploader_notas")
arquivos_2 = st.sidebar.file_uploader("Coloque o excel do AG aqui:", type=["csv", "xlsx"], key="uploader_ag")
if arquivos_1 and arquivos_2:
    if arquivos_2.name.endswith(".csv"):
        df_agexportacao = pd.read_csv(arquivos_2, sep=";", encoding="utf-8-sig")
    else:
        df_agexportacao = pd.read_excel(arquivos_2)
    dfs = []
    for final in arquivos_1:
        if final.name.endswith(".csv"):
         df_notas = pd.read_csv(final, sep=";", encoding="latin-1", on_bad_lines="skip")
        else:
         df_notas = pd.read_excel(final)
        df_notas.columns = df_notas.columns.str.upper().str.strip()
        df_notas = df_notas[colunas]
        df_notas["TIPO DE MOVIMENTAÇÃO"] = np.where(df_notas["OPERACAO ."] == 9, "SAIDA", "ENTRADA")
        df_notas["REVENDA"] = np.where(df_notas["FILIAL"] == 2, "Capitali/Cruz (CE)", "Capitali/ Itapipoca (CE)")
        dfs.append(df_notas)
    df_final_entrada = pd.concat(dfs, ignore_index=True)
    revendas = sorted(df_final_entrada["REVENDA"].dropna().unique())
    revendas_filtro = st.multiselect("Selecione a Revenda (s):", revendas)
    df_final_entrada1 = df_final_entrada[df_final_entrada["REVENDA"].isin(revendas_filtro)]
    st.header(f"NOTAS - REVENDAS: {revendas_filtro}")
    st.dataframe(df_final_entrada1, hide_index=True)

    st.divider()

    st.header(f"CONFERÊNCIA AMBEV - AG: {revendas_filtro}")

    df_age_filtrado = df_agexportacao[df_agexportacao["Nome da revenda"].isin(revendas_filtro)]

    st.dataframe(df_age_filtrado[[
    "Mês de referência",
    "Nome da revenda",
    "Nome da fábrica",
    "Código do material",
    "Descrição do material",
    "Tipo do material",
    "Saldo Ambev",
    ]], hide_index=True)

    st.divider()
    st.header("CONFERÊNCIA:")

    if not revendas_filtro:
        st.info("Selecione uma revenda lá em cima pra fazer a conferência.")
    else:
        prom = df_final_entrada1.copy()
        prom["MATERIAL"] = prom["PRODUTO"].map(MAP_MATERIAL).fillna(prom["PRODUTO"]).astype(int)
        prom["FABRICA"] = prom["NOME"].str.upper().str.strip().map(MAP_FABRICA).fillna(prom["NOME"])
        prom["QTD_PROMAX"] = np.where(prom["TIPO DE MOVIMENTAÇÃO"] == "ENTRADA", prom["QTDE"], -prom["QTDE"]) * SINAL
        prom = prom.groupby(["REVENDA", "FABRICA", "MATERIAL", "PRODUTO"], as_index=False)["QTD_PROMAX"].sum()

        ag = df_agexportacao.rename(columns={
            "Nome da revenda": "REVENDA",
            "Nome da fábrica": "FABRICA",
            "Código do material": "MATERIAL",
            "Saldo Ambev": "SALDO_AMBEV",
        })
        nomes_material = ag.drop_duplicates("MATERIAL").set_index("MATERIAL")["Descrição do material"]
        ag = ag[ag["REVENDA"].isin(revendas_filtro)]
        ag = ag.groupby(["REVENDA", "FABRICA", "MATERIAL"], as_index=False)["SALDO_AMBEV"].sum()


        conf = ag.merge(prom, on=["REVENDA", "FABRICA", "MATERIAL"], how="outer", indicator=True)
        conf["DESCRIÇÃO"] = conf["MATERIAL"].map(nomes_material)
        MAP_INVERSO = {ambev: promax for promax, ambev in MAP_MATERIAL.items()}
        conf["PRODUTO_PROMAX"] = conf["PRODUTO"].fillna(conf["MATERIAL"].map(MAP_INVERSO))
        conf["DIFERENÇA"] = conf["QTD_PROMAX"].fillna(0) - conf["SALDO_AMBEV"].fillna(0)

        ST_OK = "✅ OK"
        ST_DIV = "⚠️ DIVERGENTE"
        ST_PROMAX = "🟡 SÓ NO PROMAX"
        ST_AMBEV = "🔵 SÓ NA AMBEV"

        conf["STATUS"] = np.select(
            [
                conf["_merge"] == "right_only",
                conf["_merge"] == "left_only",
                conf["DIFERENÇA"].abs() < 0.01,
            ],
            [ST_PROMAX, ST_AMBEV, ST_OK],
            default=ST_DIV,
        )
        conf = conf[["REVENDA", "FABRICA", "PRODUTO_PROMAX", "MATERIAL", "DESCRIÇÃO", "SALDO_AMBEV", "QTD_PROMAX", "DIFERENÇA", "STATUS"]]

        c1, c2, c3, c4 = st.columns(4)
        c1.metric(ST_OK, int((conf["STATUS"] == ST_OK).sum()))
        c2.metric(ST_DIV, int((conf["STATUS"] == ST_DIV).sum()))
        c3.metric(ST_PROMAX, int((conf["STATUS"] == ST_PROMAX).sum()))
        c4.metric(ST_AMBEV, int((conf["STATUS"] == ST_AMBEV).sum()))

        conferencia = conf.copy()
        status_filtro = st.multiselect("Filtrar status:", sorted(conf["STATUS"].unique()), default=sorted(conf["STATUS"].unique()))
        conf = conf[conf["STATUS"].isin(status_filtro)]

        cores = {
            ST_OK: "background-color: #1b5e20",
            ST_DIV: "background-color: #b71c1c",
            ST_PROMAX: "background-color: #8d6e00",
            ST_AMBEV: "background-color: #0d47a1",
        }

        tabela = conf.style.apply(lambda linha: [cores.get(linha["STATUS"], "")] * len(linha), axis=1)
        tabela = tabela.format(na_rep="—")
        tabela = tabela.format({"PRODUTO_PROMAX": "{: .0f}", "SALDO_AMBEV": "{:.2f}", "QTD_PROMAX": "{:.2f}", "DIFERENÇA": "{:.2f}"}, na_rep="—")
        
        st.dataframe(tabela, hide_index=True, use_container_width=True)
        
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as w:
           conferencia.to_excel(w, sheet_name="TUDO", index=False)
           abas = {"OK": ST_OK, "DIVERGENTE": ST_DIV, "SO_PROMAX": ST_PROMAX, "SO_AMBEV": ST_AMBEV}
           for nome_aba, status in abas.items():
              conferencia[conferencia["STATUS"] == status].to_excel(w, sheet_name=nome_aba, index=False)
        st.download_button(label="Baixe a CONFERÊNCIA, separado por status:", data=buffer.getvalue(), file_name="conferencia_promax_ambev.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

else:
    st.info("Coloque as notas do Promax e o arquivo do AG na barra lateral pra começar.")

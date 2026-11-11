import pandas as pd
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
    27983: 38719,   # GFA VIDRO 635ML ÂMBAR <- conferir
}

MAP_FABRICA = {
    "FAB. AQUIRAZ": "F. Aquiraz",
    "F. AQUIRAZ": "F. Aquiraz",
    "AMBEV - F. AQUIRAZ": "F. Aquiraz",
    "F. TERESINA": "F. Teresina",
    "FILIAL TERESINA": "F. Teresina",
    "F. PERNAMBUCO": "F. Pernambuco",
    "F. A. CLARAS": "F. A. Claras",
    "FILIAL ITAPISSUMA": "F. Pernambuco",  # nota 1132491 (Promax) = F. Pernambuco no extrato
    "CDR PARAIBA": "F. Fonte Mata",         # nota 184526 (Promax) = F. Fonte Mata no extrato
}

colunas_excluir = [
    "Número do Documento de Material",
    "Tipo de Movimento",
    "Descrição do Movimento",
    "Texto de cabeçalho do documento",
    "Referência do Documento de Material"
]

ST_OK = "✅ OK"
ST_DIV = "⚠️ DIVERGENTE"
ST_PROMAX = "🟡 SÓ NO PROMAX"
ST_AMBEV = "🔵 SÓ NA AMBEV"

cores = {
    ST_OK: "background-color: #1b5e20",
    ST_DIV: "background-color: #b71c1c",
    ST_PROMAX: "background-color: #8d6e00",
    ST_AMBEV: "background-color: #0d47a1",
}

def br(n):
    # Python sempre formata milhar com "," (padrão americano); troco por "." (padrão BR)
    return f"{n:,.0f}".replace(",", ".")


st.title("PRODUTOS AG - BALANÇO NOTAS DE ENTRADA E SAIDA (PROMAX E AMBEV)")

arquivos_1 = st.sidebar.file_uploader("Coloque suas notas do promax:", type=["csv", "xlsx"], accept_multiple_files=True, key="uploader_notas")
arquivos_2 = st.sidebar.file_uploader("Coloque o extrato do AG aqui:", type=["csv", "xlsx"], key="uploader_ag")

if arquivos_1 and arquivos_2:
    if arquivos_2.name.endswith(".csv"):
        df_agexportacao = pd.read_csv(arquivos_2, sep=";", encoding="utf-8-sig")
    else:
        df_agexportacao = pd.read_excel(arquivos_2)
    df_agexportacao["Saldo Ambev"] = df_agexportacao["Quantidade de Crédito"] - df_agexportacao["Quantidade de Débito"]
    df_agexportacao = df_agexportacao.drop(columns=colunas_excluir, errors="ignore")

    # o extrato usa outros nomes de coluna; renomeio aqui pra o resto do código continuar igual
    df_agexportacao = df_agexportacao.rename(columns={
        "Nome do Parceiro": "Nome da revenda",
        "Nome": "Nome da fábrica",
        "Material": "Código do material",
        "Descrição do Material": "Descrição do material",
        "Tipo de Material": "Tipo do material",
    })
    df_agexportacao["Data de Lançamento"] = pd.to_datetime(df_agexportacao["Data de Lançamento"], dayfirst=True, errors="coerce")
    df_agexportacao["Mês de referência"] = df_agexportacao["Data de Lançamento"].dt.strftime("%m/%Y")

    dfs = []
    for final in arquivos_1:
        if final.name.endswith(".csv"):
            # thousands/decimal: o Promax usa "." de milhar (49.680 = 49680)
            df_notas = pd.read_csv(final, sep=";", encoding="latin-1", on_bad_lines="skip", thousands=".", decimal=",")
        else:
            df_notas = pd.read_excel(final)
        df_notas.columns = df_notas.columns.str.upper().str.strip()
        df_notas = df_notas[colunas]
        df_notas["TIPO DE MOVIMENTAÇÃO"] = np.where(df_notas["OPERACAO ."] == 9, "SAIDA", "ENTRADA")
        df_notas["REVENDA"] = np.where(df_notas["FILIAL"] == 2, "Capitali/Cruz (CE)", "Capitali/ Itapipoca (CE)")
        dfs.append(df_notas)
    df_final_entrada = pd.concat(dfs, ignore_index=True)

    # sem renomear: DT. OPERACAO continua existindo, e a EMISSAO é a data que bate com o extrato do AG
    df_final_entrada["DT. OPERACAO"] = pd.to_datetime(df_final_entrada["DT. OPERACAO"], dayfirst=True, errors="coerce")
    df_final_entrada["EMISSAO"] = pd.to_datetime(df_final_entrada["EMISSAO"], dayfirst=True, errors="coerce")

    data_min = df_final_entrada["EMISSAO"].min().date()
    data_max = df_final_entrada["EMISSAO"].max().date()

    col1, col2, col3 = st.columns(3)
    filtro_datamin = col1.date_input("De", value=data_min)
    filtro_datamax = col2.date_input("Até", value=data_max)
    revendas = sorted(df_final_entrada["REVENDA"].dropna().unique())
    revendas_filtro = col3.multiselect("Selecione a Revenda (s):", revendas)

    df_final_entrada1 = df_final_entrada[
        df_final_entrada["REVENDA"].isin(revendas_filtro)
        & df_final_entrada["EMISSAO"].dt.date.between(filtro_datamin, filtro_datamax)
    ]
    df_ag_filtro = df_agexportacao[
        df_agexportacao["Nome da revenda"].isin(revendas_filtro)
        & df_agexportacao["Data de Lançamento"].dt.date.between(filtro_datamin, filtro_datamax)
    ]
    st.header(f"NOTAS - REVENDAS: {revendas_filtro}")
    st.dataframe(df_final_entrada1, hide_index=True)

    st.divider()

    st.header(f"CONFERÊNCIA AMBEV - AG: {revendas_filtro}")

    st.dataframe(df_ag_filtro[[
        "Data de Lançamento",
        "Número da NF-e",
        "Mês de referência",
        "Nome da revenda",
        "Nome da fábrica",
        "Código do material",
        "Descrição do material",
        "Tipo do material",
        "Saldo Ambev",
    ]], hide_index=True)

    st.divider()
    st.header("CONFERÊNCIA POR NOTA E PRODUTO:")

    if not revendas_filtro:
        st.info("Selecione uma revenda lá em cima pra fazer a conferência.")
    else:
        # ---------- CONFERÊNCIA POR NOTA + DATA (Promax x extrato do AG) ----------
        st.divider()

        ext = df_ag_filtro.dropna(subset=["Número da NF-e"]).copy()
        # entrada do Promax vira débito no AG, então comparo em valor absoluto
        ext["QTD_EXTRATO"] = ext["Quantidade de Crédito"] + ext["Quantidade de Débito"]
        ext["MOV_EXTRATO"] = np.where(ext["Quantidade de Débito"] > 0, "ENTRADA", "SAIDA")  # débito = entrada no Promax
        ext = ext.rename(columns={"Nome da revenda": "REVENDA", "Número da NF-e": "NOTA", "Código do material": "MATERIAL"})
        ext["NOTA"] = ext["NOTA"].astype("int64")
        ext_nota = ext.groupby(["REVENDA", "NOTA", "MATERIAL"], as_index=False).agg(
            DATA_EXTRATO=("Data de Lançamento", "min"),
            FABRICA_EXTRATO=("Nome da fábrica", "first"),
            DESCRIÇÃO=("Descrição do material", "first"),
            QTD_EXTRATO=("QTD_EXTRATO", "sum"),
        )

        pn = df_final_entrada1.copy()
        pn["MATERIAL"] = pn["PRODUTO"].map(MAP_MATERIAL).fillna(pn["PRODUTO"]).astype(int)
        pn["FABRICA_PROMAX"] = pn["NOME"].str.upper().str.strip().map(MAP_FABRICA).fillna(pn["NOME"].str.strip())
        pn = pn.groupby(["REVENDA", "NOTA", "MATERIAL"], as_index=False).agg(
            TIPO=("TIPO DE MOVIMENTAÇÃO", "first"),
            DATA_PROMAX=("EMISSAO", "min"),
            FABRICA_PROMAX=("FABRICA_PROMAX", "first"),
            PRODUTO_PROMAX=("PRODUTO", "first"),
            DESC_PROMAX=("DESCRIÇÃO", "first"),
            QTD_PROMAX=("QTDE", "sum"),
        )

        conf_nota = ext_nota.merge(pn, on=["REVENDA", "NOTA", "MATERIAL"], how="outer", indicator=True)
        conf_nota["DIFERENÇA"] = conf_nota["QTD_PROMAX"].fillna(0) - conf_nota["QTD_EXTRATO"].fillna(0)
        conf_nota["STATUS"] = np.select(
            [
                conf_nota["_merge"] == "right_only",
                conf_nota["_merge"] == "left_only",
                conf_nota["DIFERENÇA"].abs() < 0.01,
            ],
            [ST_PROMAX, ST_AMBEV, ST_OK],
            default=ST_DIV,
        )
        conf_nota = conf_nota.drop(columns="_merge")
        MAP_INVERSO = {ambev: promax for promax, ambev in MAP_MATERIAL.items()}
        conf_nota["DESCRIÇÃO"] = conf_nota["DESCRIÇÃO"].fillna(conf_nota["DESC_PROMAX"])
        conf_nota["PRODUTO_PROMAX"] = conf_nota["PRODUTO_PROMAX"].fillna(conf_nota["MATERIAL"].map(MAP_INVERSO))
        conf_nota = conf_nota[[
            "REVENDA", "NOTA", "DATA_PROMAX", "DATA_EXTRATO", "TIPO",
            "FABRICA_PROMAX", "FABRICA_EXTRATO",
            "PRODUTO_PROMAX", "MATERIAL", "DESCRIÇÃO",
            "QTD_PROMAX", "QTD_EXTRATO", "DIFERENÇA", "STATUS",
        ]]

        # ---------- RESUMO DO PERÍODO (estilo extrato de banco) ----------
        st.subheader("RESUMO DO PERÍODO")
        st.caption(f"De {filtro_datamin:%d/%m/%Y} até {filtro_datamax:%d/%m/%Y} — {', '.join(revendas_filtro)}")

        def notas(df, col, mov):
            return df.loc[df[col] == mov, "NOTA"].nunique()

        pe, ps = notas(pn, "TIPO", "ENTRADA"), notas(pn, "TIPO", "SAIDA")
        ae, as_ = notas(ext, "MOV_EXTRATO", "ENTRADA"), notas(ext, "MOV_EXTRATO", "SAIDA")

        r1 = st.columns(4)
        r1[0].metric("Notas de ENTRADA no Promax", pe)
        r1[1].metric("Notas de ENTRADA no AG", ae, delta=int(ae - pe), delta_color="red")
        r1[2].metric("Notas de SAÍDA no Promax", ps)
        r1[3].metric("Notas de SAÍDA no AG", as_, delta=int(as_ - ps), delta_color="red")

        r2 = st.columns(4)
        qpe = pn.loc[pn["TIPO"] == "ENTRADA", "QTD_PROMAX"].sum()
        qae = ext.loc[ext["MOV_EXTRATO"] == "ENTRADA", "QTD_EXTRATO"].sum()
        qps = pn.loc[pn["TIPO"] == "SAIDA", "QTD_PROMAX"].sum()
        qas = ext.loc[ext["MOV_EXTRATO"] == "SAIDA", "QTD_EXTRATO"].sum()
        r2[0].metric("Qtd ENTRADAS Promax", br(qpe))
        r2[1].metric("Qtd ENTRADAS AG", br(qae), delta=br(qae - qpe), delta_color="red")
        r2[2].metric("Qtd SAÍDAS Promax", br(qps))
        r2[3].metric("Qtd SAÍDAS AG", br(qas), delta=br(qas - qps), delta_color="red")

        # por produto: entradas e saídas de cada lado, e a diferença
        prod_prom = pn.pivot_table(index="MATERIAL", columns="TIPO", values="QTD_PROMAX", aggfunc="sum", fill_value=0)
        prod_prom = prod_prom.reindex(columns=["ENTRADA", "SAIDA"], fill_value=0)
        prod_prom.columns = ["ENTRADAS_PROMAX", "SAIDAS_PROMAX"]
        prod_ag = ext.pivot_table(index="MATERIAL", columns="MOV_EXTRATO", values="QTD_EXTRATO", aggfunc="sum", fill_value=0)
        prod_ag = prod_ag.reindex(columns=["ENTRADA", "SAIDA"], fill_value=0)
        prod_ag.columns = ["ENTRADAS_AG", "SAIDAS_AG"]
        resumo = prod_prom.join(prod_ag, how="outer").fillna(0).reset_index()
        resumo["DIF_ENTRADAS"] = resumo["ENTRADAS_PROMAX"] - resumo["ENTRADAS_AG"]
        resumo["DIF_SAIDAS"] = resumo["SAIDAS_PROMAX"] - resumo["SAIDAS_AG"]
        nomes = conf_nota.drop_duplicates("MATERIAL").set_index("MATERIAL")["DESCRIÇÃO"]
        resumo.insert(1, "DESCRIÇÃO", resumo["MATERIAL"].map(nomes))
        st.dataframe(resumo.style.format({c: br for c in resumo.columns[2:]}), hide_index=True, use_container_width=True)

        st.subheader("DETALHE POR NOTA E PRODUTO")
        n1, n2, n3, n4 = st.columns(4)
        n1.metric(ST_OK, int((conf_nota["STATUS"] == ST_OK).sum()))
        n2.metric(ST_DIV, int((conf_nota["STATUS"] == ST_DIV).sum()))
        n3.metric(ST_PROMAX, int((conf_nota["STATUS"] == ST_PROMAX).sum()))
        n4.metric(ST_AMBEV, int((conf_nota["STATUS"] == ST_AMBEV).sum()))

        status_nota = st.multiselect("Filtrar status (notas):", sorted(conf_nota["STATUS"].unique()), default=sorted(conf_nota["STATUS"].unique()))
        conf_nota_vis = conf_nota[conf_nota["STATUS"].isin(status_nota)]

        tabela_nota = conf_nota_vis.style.apply(lambda linha: [cores.get(linha["STATUS"], "")] * len(linha), axis=1)
        tabela_nota = tabela_nota.format({
            "DATA_PROMAX": "{:%d/%m/%Y}",
            "DATA_EXTRATO": "{:%d/%m/%Y}",
            "PRODUTO_PROMAX": "{:.0f}",
            "QTD_PROMAX": "{:.2f}",
            "QTD_EXTRATO": "{:.2f}",
            "DIFERENÇA": "{:.2f}",
        }, na_rep="—")
        st.dataframe(tabela_nota, hide_index=True, use_container_width=True)

        buffer_nota = io.BytesIO()
        with pd.ExcelWriter(buffer_nota, engine="openpyxl") as w:
            conf_nota.to_excel(w, sheet_name="TUDO", index=False)
            abas = {"OK": ST_OK, "DIVERGENTE": ST_DIV, "SO_PROMAX": ST_PROMAX, "SO_EXTRATO": ST_AMBEV}
            for nome_aba, status in abas.items():
                conf_nota[conf_nota["STATUS"] == status].to_excel(w, sheet_name=nome_aba, index=False)
        st.download_button(label="Baixe a CONFERÊNCIA POR NOTA, separado por status:", data=buffer_nota.getvalue(), file_name="conferencia_notas_extrato.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="download_nota")

else:
    st.info("Coloque as notas do Promax e o arquivo do AG na barra lateral pra começar.")

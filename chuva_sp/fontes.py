"""Bases de dados de referência (mesma lista do arquivo R/00_fontes_dados.R)."""
from __future__ import annotations

import pandas as pd

# Lista indicada pelo usuário – mantida como está
BASES_INDICADAS = [
    ("EPAGRI/CIRAM", "https://ciram.epagri.sc.gov.br/index.php/imagem-de-satelite/", "Imagens de satélite"),
    ("NOAA Satellites", "https://www.nesdis.noaa.gov/", "Satélites e produtos da NOAA/NESDIS"),
    ("TRMM", "https://gpm.nasa.gov/missions/trmm", "Tropical Rainfall Measuring Mission (1997–2015)"),
    ("DAEE", "https://sibh.sp.gov.br/", "Rede pluviométrica do Estado de SP (SIBH)"),
    ("ANA (todas as estações superficiais convencionais e automáticas)", "https://www.snirh.gov.br/hidroweb/", "HidroWeb / SNIRH"),
]

# Fontes efetivamente acessadas pelo programa
BASES_USADAS = [
    ("CHIRPS v3.0 RNL (CHC/UCSB; cópia WFP no Source Cooperative)", "https://source.coop/wfp/chirps-rnl-daily", "satélite"),
    ("GPM IMERG v07 Late (NASA; cópia dynamical.org)", "https://dynamical.org/catalog/nasa-imerg-analysis-late/", "satélite"),
    ("PERSIANN-CDR (NOAA CDR / NODD-AWS)", "https://registry.opendata.aws/noaa-cdr-precip-persiann/", "satélite"),
    ("CMORPH CDR (NOAA CDR / NODD-AWS)", "https://registry.opendata.aws/noaa-cdr-precip-cmorph/", "satélite"),
    ("GPCP mensal e diário (NOAA CDR / NODD-AWS)", "https://registry.opendata.aws/noaa-cdr-precip-gpcp-monthly/", "satélite + pluviômetros"),
    ("GHCN-Daily (NOAA) – postos ANA e DAEE de SP", "https://registry.opendata.aws/noaa-ghcn/", "estações"),
    ("INMET – estações automáticas (portal de dados históricos)", "https://portal.inmet.gov.br/dadoshistoricos", "estações (código pronto)"),
    ("Limites das UGRHIs (DAEE/SIBH)", "https://sibh.sp.gov.br/", "vetor"),
]


def tabela() -> pd.DataFrame:
    a = pd.DataFrame(BASES_INDICADAS, columns=["Base", "Endereço", "Descrição"])
    a.insert(0, "Grupo", "Bases indicadas")
    b = pd.DataFrame(BASES_USADAS, columns=["Base", "Endereço", "Descrição"])
    b.insert(0, "Grupo", "Acessadas pelo programa")
    return pd.concat([a, b], ignore_index=True)

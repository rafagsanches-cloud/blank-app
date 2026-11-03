"""Configurações gerais: caminhos, período, área de estudo e catálogo de produtos."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "dados"
BRUTOS = DADOS / "brutos"
UGRHI_DIR = DADOS / "ugrhi"
CACHE = DADOS / "cache"            # arquivos intermediários (não versionados)
PROCESSADOS = DADOS / "processados"  # séries finais em parquet (lidas pelo app)
SAIDAS = RAIZ / "saidas"            # pastas de trabalho do Excel

UGRHI_CSV = BRUTOS / "sibh_ugrhis_sp.csv"
UGRHI_GPKG = UGRHI_DIR / "UGRHI_SP.gpkg"

DATA_INICIO = dt.date(1980, 1, 1)
DATA_FIM = dt.date.today()

# Retângulo envolvente do Estado de SP com margem (lon_min, lat_min, lon_max, lat_max)
BBOX_SP = (-53.4, -25.6, -43.9, -19.5)

# Fuso usado para a coluna de hora local (horário de Brasília, sem horário de verão)
FUSO_LOCAL_H = -3

# Catálogo dos produtos de precipitação por satélite (tabela pedida + complementares)
PRODUTOS = {
    "CHIRPS": {
        "nome": "CHIRPS v3.0 (RNL)",
        "sensor": "Infravermelho + Estações",
        "inicio": "1981-01-01",
        "resolucao": "0,05° (~5 km)",
        "escala_nativa": "diária",
        "foco": "Monitoramento agrícola e tendências de seca a longo prazo.",
        "fonte": "Climate Hazards Center (UCSB) / WFP – Source Cooperative (S3)",
        "url": "https://source.coop/wfp/chirps-rnl-daily",
        "citacao": "Climate Hazards Center CHIRPS3 Data Repository, https://doi.org/10.15780/G2JQ0P",
    },
    "IMERG": {
        "nome": "GPM IMERG v07 Late Run",
        "sensor": "Micro-ondas + Radar (+ IR)",
        "inicio": "1998-01-01",
        "resolucao": "0,1° (~10 km)",
        "escala_nativa": "30 minutos",
        "foco": "Precisão física de tempestades, neve e meteorologia global.",
        "fonte": "NASA GPM / dynamical.org (Icechunk Zarr, S3)",
        "url": "https://dynamical.org/catalog/nasa-imerg-analysis-late/",
        "citacao": "Huffman et al. (2023) GPM IMERG Late Precipitation L3 Half Hourly 0.1° V07",
    },
    "PERSIANN": {
        "nome": "PERSIANN-CDR v01r01",
        "sensor": "Infravermelho + IA (redes neurais)",
        "inicio": "1983-01-01",
        "resolucao": "0,25° (~25 km)",
        "escala_nativa": "diária",
        "foco": "Padrões de nuvens e estimativas baseadas em aprendizado de máquina.",
        "fonte": "CHRS/UC Irvine – NOAA CDR (NODD, S3)",
        "url": "https://www.ncei.noaa.gov/products/climate-data-records/precipitation-persiann",
        "citacao": "Ashouri et al. (2015) BAMS, doi:10.1175/BAMS-D-13-00068.1",
    },
    "CMORPH": {
        "nome": "CMORPH CDR v1.0 (ajustado)",
        "sensor": "Micro-ondas 'morfado' (vetores de movimento IR)",
        "inicio": "1998-01-01",
        "resolucao": "0,25° (~25 km) horário | 8 km/30 min no original",
        "escala_nativa": "horária",
        "foco": "Movimento contínuo de precipitação e taxas de chuva em tempo real.",
        "fonte": "NOAA CPC – NOAA CDR (NODD, S3)",
        "url": "https://www.ncei.noaa.gov/products/climate-data-records/precipitation-cmorph",
        "citacao": "Xie et al. (2017) J. Hydrometeor., doi:10.1175/JHM-D-16-0168.1",
    },
    "GPCP": {
        "nome": "GPCP v2.3 mensal (2,5°) / v1.3 diário (1°)",
        "sensor": "Satélite + pluviômetros (combinado)",
        "inicio": "1979-01-01",
        "resolucao": "2,5° mensal | 1° diário (desde 1996)",
        "escala_nativa": "mensal / diária",
        "foco": "Referência climática de longo prazo (cobre 1980).",
        "fonte": "NASA/GSFC – NOAA CDR (NODD, S3)",
        "url": "https://www.ncei.noaa.gov/products/climate-data-records/precipitation-gpcp-monthly",
        "citacao": "Adler et al. (2018) Atmosphere, doi:10.3390/atmos9040138",
    },
}

# Produtos da tabela original (ordem de apresentação)
PRODUTOS_TABELA = ["CHIRPS", "IMERG", "PERSIANN", "CMORPH"]


def garantir_pastas() -> None:
    for p in (CACHE, PROCESSADOS, SAIDAS, UGRHI_DIR):
        p.mkdir(parents=True, exist_ok=True)

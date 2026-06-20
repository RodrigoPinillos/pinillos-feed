#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Genera el feed de INVENTARIO LOCAL para Google Merchant Center.
Toma los productos del feed principal (google_merchant_feed_pinillos.tsv) y los
marca como disponibles en la tienda física.

Requiere el código de tienda (store_code) que sale al vincular tu Perfil de
Empresa de Google con Merchant Center. Se puede pasar por variable de entorno
STORE_CODE o como 1er argumento.

Uso:  STORE_CODE=tu_codigo python3 build_local_inventory.py [salida.tsv]
"""
import csv, os, sys

STORE_CODE = (sys.argv[2] if len(sys.argv) > 2 else os.environ.get("STORE_CODE", "")).strip()
SRC = "google_merchant_feed_pinillos.tsv"
OUT = sys.argv[1] if len(sys.argv) > 1 else "local_inventory_feed_pinillos.tsv"

if not STORE_CODE:
    sys.exit("ERROR: falta STORE_CODE (env var o 2º argumento). "
             "Es el código de tienda de tu Perfil de Empresa en Merchant Center.")

if not os.path.exists(SRC):
    sys.exit(f"ERROR: no encuentro {SRC}. Corré primero build_feed.py.")

prods = list(csv.DictReader(open(SRC, encoding="utf-8"), delimiter="\t"))

# Atributos del feed de inventario local:
#   store_code (req) | id (req, = id del feed principal) | availability (req)
#   price (opcional, mismo precio) | quantity (opcional, no lo inventamos)
cols = ["store_code", "id", "availability", "price"]
n = 0
with open(OUT, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=cols, delimiter="\t")
    w.writeheader()
    for p in prods:
        w.writerow({
            "store_code": STORE_CODE,
            "id": p["id"],
            "availability": "in_stock",   # todo el catálogo disponible en el local
            "price": p["price"],
        })
        n += 1

print(f"OK -> {OUT}  ({n} productos en tienda {STORE_CODE})")

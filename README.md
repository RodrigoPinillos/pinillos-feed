# Feed Google Merchant Center — Pinillos

Genera automáticamente el feed de productos de **https://www.pinillos.com.ar/** para Google Merchant Center.

## Qué hace
`build_feed.py` scrapea el catálogo en vivo (las 7 páginas del listado), entra a cada ficha y arma
`google_merchant_feed_pinillos.tsv` con todos los campos que pide Google.

- **Precio:** final con **+21% IVA** incluido (`NNNNN.NN ARS`).
- **Marca:** la de la ficha; con overrides manuales (ver `BRAND_OVERRIDE` en el script).
- **identifier_exists:** `no` (productos sin GTIN).
- **availability:** `in_stock`.

## Automatización (GitHub Actions)
`.github/workflows/feed.yml` corre **todos los lunes** (06:00 UTC), regenera el TSV y lo commitea.
También se puede ejecutar a mano desde la pestaña **Actions → Run workflow**.

## URL del feed (para Google Merchant Center)
El archivo queda público en:

```
https://raw.githubusercontent.com/RodrigoPinillos/pinillos-feed/main/google_merchant_feed_pinillos.tsv
```

En Merchant Center: **Feeds → Agregar feed → Argentina / Español / ARS → "Recuperación programada (scheduled fetch)"**,
pegás esa URL y elegís frecuencia **semanal**.

## Correr a mano (local)
```bash
python3 build_feed.py
```
Sin dependencias (solo Python 3 estándar).

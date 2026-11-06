# Revisión previa a la visibilidad pública

El repositorio [jgangini/aidp-ai-gods-eye-view](https://github.com/jgangini/aidp-ai-gods-eye-view) tiene visibilidad **PUBLIC**, verificada mediante GitHub y peticiones HTTP sin autenticación. El cambio fue autorizado explícitamente por el propietario. No se confirmó ningún secreto en el alcance revisado.

Este documento conserva evidencia de publicación. El funcionamiento del producto se describe en el [README](../../README.md), los [contratos](../contracts.md) y la [operación](../operations.md).

## Historial y archivos

Snapshot previo a la actualización documental: `149ef9a45fa405ce4b49086ae69ad6572f02a89a`.

- Ocho commits alcanzables, seis refs —incluido `origin/HEAD`—, 589 blobs únicos y 518 rutas históricas; 51.278.089 bytes revisados.
- Se incluyeron archivos eliminados, mensajes de commits, contenido binario y los tags ligeros `v1.0.0`, `v1.0.1`, `v1.0.2`. El remoto solo tenía `main` y esos tres tags; no había PRs.
- Búsqueda por firmas de claves/tokens, entropía y contexto de asignaciones y URLs. No se encontraron credenciales OCI, tokens privados confirmados, wallets ni estado Terraform versionado.
- Las coincidencias correspondían a marcadores PEM incompletos de pruebas negativas, URLs ficticias, campos de proveedores, comentarios y hashes de dependencias.
- Se conserva la metadata normal de autor/committer. No se reescribió el historial.

La actualización posterior contiene únicamente documentación. Su diff y archivos nuevos se revisaron con el escáner del repositorio y comprobaciones de enlaces; no se incorporaron archivos ignorados, credenciales ni datos de ejecución.

## Releases e imágenes

Se verificaron los 18 assets de las tres releases contra sus tamaños y SHA-256 remotos. Se leyeron las nueve imágenes Docker **sin ejecutarlas**, incluyendo capas anteriores que podrían contener archivos sobrescritos o eliminados:

| Alcance | Cantidad |
| --- | ---: |
| Imágenes distribuidas | 9 |
| Capas únicas inspeccionadas | 78 |
| Archivos de capas inspeccionados | 230.573 |
| Bytes de contenido de archivos examinados | 4.353.223.218 |
| Configuraciones de imagen, con ID coincidente | 9 |
| Archivos de metadata Docker revisados | 36 |

Los nombres de variables de entorno de las imágenes corresponden a valores públicos de build/runtime esperados. La búsqueda de rutas de credenciales solo señaló tres copias idénticas de `.env.example`; los campos de claves/tokens de proveedor estaban vacíos. Un parámetro numérico de límite de contexto no es una credencial.

Las 82 coincidencias de firmas y 174 coincidencias contextuales se clasificaron mediante contexto y hashes, sin imprimir sus valores:

- Los bloques PEM de `libgnutls.so.30.34.3` son fixtures públicos de auto-prueba. Los nueve bloques encontrados coinciden por SHA-256 con el [archivo oficial de GnuTLS fijado a un commit](https://gitlab.com/gnutls/gnutls/-/blob/ca61668d7764fc29fb4cc2aa396cb035e176636d/lib/crypto-selftests-pk.c#L47). No son claves de una instalación de God’s Eye View.
- Las coincidencias AWS dentro de Node/Flow y libunistring pertenecen a contenido WASM codificado y tablas Unicode, no a asignaciones de credenciales.
- Los JWT corresponden al token demo distribuido por Cesium y a fixtures de validación. Cesium documenta el [token de evaluación incluido en su SDK](https://cesium.com/learn/cesiumjs/ref-doc/Ion.html); no se usó contra el servicio ni se trató como una credencial de producción.
- Las asignaciones y URLs restantes corresponden a documentación SDK, enums, mensajes de error ZIP/Cesium, estados de tokenizer, ejemplos y pruebas negativas. La revisión adicional cerró 90 coincidencias deduplicadas y contrastó 56 hashes de archivo.

## Comprobación de exposición

- API del repositorio sin autenticación: HTTP 200, `private=false`, `visibility=public`.
- Lista de releases sin autenticación: HTTP 200.
- Descarga sin autenticación de `gods-eye-view-api-release.json` de `v1.0.2`: HTTP 200 y SHA-256 coincidente.
- Se conservaron los IDs, tamaños, digests e inmutabilidad de las tres releases y sus 18 assets. No se reconstruyeron imágenes, cambiaron tags ni editaron notas inmutables.

## Límites

La revisión por firmas, entropía y contexto reduce el riesgo de exposición; no demuestra ausencia absoluta de todo secreto en contenido opaco. No incluyó OCR, validación remota de credenciales, datos OCI ni volúmenes de instalaciones. No se leyeron archivos `.oci` del equipo, no se ejecutaron contenedores ni se realizaron operaciones OCI.

La publicidad no acredita seguridad funcional, corrección de avisos de dependencias ni aceptación nativa. La [revisión de dependencias](native-dependency-review.md) y los [recibos de releases](../release-contract.md) permanecen separados de esta comprobación.

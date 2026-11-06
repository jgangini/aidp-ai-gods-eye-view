# Entrega de assets verificados

El control plane de Deploy Studio resuelve el repositorio público y una release estable inmutable, verifica tag/commit y metadata GitHub, y entrega archivos locales al hook. Si utiliza autorización GitHub, la conserva en el control plane. El producto no recibe tokens, URLs bearer ni headers GitHub.

## Archivos requeridos

El [manifiesto](../terraform/deploy-studio.json) declara seis `release_assets` por fase. Preflight recibe tres JSON descargados y metadata de los tres gzip; post-apply recibe los seis archivos.

| Componente | Manifiesto | Imagen gzip | Máximo gzip |
| --- | --- | --- | --- |
| API | `gods-eye-view-api-release.json` | `gods-eye-view-api-image-amd64.tar.gz` | 512 MiB |
| Visor | `gods-eye-view-release.json` | `gods-eye-view-image-amd64.tar.gz` | 1 GiB |
| Gateway | `gods-eye-view-gateway-release.json` | `gods-eye-view-gateway-image-amd64.tar.gz` | 128 MiB |

Cada JSON permite 65.536 bytes. Los assets se almacenan fuera de la extracción de fuentes; no consumen su límite de 10 MiB. La fuente tiene límites separados de 100 MiB de archivo, 250 archivos y 10 MiB extraídos en CTN.

## Contexto del runner

`context.release_assets` es un campo confiable del runner, no un input del formulario:

```json
{
  "schema_version": 1,
  "repository": "https://github.com/jgangini/aidp-ai-gods-eye-view",
  "ref": "v1.0.2",
  "commit_sha": "<40 hex>",
  "release_id": 123,
  "assets": {
    "gods-eye-view-api-release.json": {
      "asset_id": 456,
      "size": 561,
      "sha256": "<64 hex>",
      "path": "<ruta local absoluta readonly>"
    }
  }
}
```

El ejemplo abrevia los seis nombres. IDs y tamaños son ilustrativos. `path` está presente solo cuando el control plane descargó/verificó ese archivo. El consumidor exige repositorio/ref/commit iguales a `context.source` y a `inputs.release_tag/source_commit_sha`, schema 1, IDs positivos distintos, seis nombres exactos, límites y hashes válidos.

Cada JSON schema 1/updater_protocol 1 vincula repositorio, release, commit, nombre/hash del gzip, plataforma `linux/amd64`, tag canónico `<componente>:<commit>` e ID `sha256:...`.

## Revalidación y staging

- `inspect_handoff(context)` verifica JSON locales, semántica de manifiestos y metadata de imágenes. También verifica cualquier gzip cuyo path se entregue.
- `inspect_handoff(context, require_archives=True)` exige y verifica todos los gzip antes de iniciar instalación.
- `stage_handoff(context, storage)` verifica snapshots de los seis archivos antes del primer upload; publica tres gzip mediante CAS y rechaza objetos existentes incompatibles.

Se rechazan rutas relativas, directorios y symlinks/reparse points, incluidos ancestros. Las cargas usan snapshots verificados para que cambiar un path original no altere los bytes publicados. Un handoff ausente o inválido no permite crear el journal ni recursos nativos.

## Contrato de la VM

El staging devuelve tres descriptores, con namespace/bucket obtenidos de outputs Terraform:

```json
{
  "component": "api",
  "object_name": "releases/<commit>/gods-eye-view-api-image-amd64.tar.gz",
  "archive_sha256": "<64 hex>",
  "image_id": "sha256:<64 hex>",
  "image_tag": "gods-eye-view-api:<commit>"
}
```

Visor y gateway usan sus prefijos de la tabla. La VM lee objetos mediante instance principal restringido, verifica SHA antes de `docker load` e ID/plataforma después. Compose usa IDs locales y `pull_policy: never`. El receptor systemd y los recibos activos controlan la activación; véase [operación](operations.md).

`vm-bootstrap.zip` se construye desde cuatro archivos explícitos del código fijado. Preflight calcula su objeto y SHA; post-apply valida/publica esos bytes en el bucket operativo. Es independiente de las imágenes y no es un séptimo asset de release.

## Alcance

La publicidad del código no vuelve públicos buckets, controles, claves ni datos OCI. La integración exige una versión de CTN que implemente este contrato. Aceptar el schema o verificar archivos localmente no demuestra instalación, IAM, capacidad o publicación nativa en un entorno OCI. Los [recibos de releases](release-contract.md) conservan evidencias separadas del procedimiento operativo.

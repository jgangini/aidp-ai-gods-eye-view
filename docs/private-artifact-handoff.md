# Handoff privado de assets

El control plane CTN conserva la autorización GitHub y entrega archivos verificados al hook. El producto consume metadata y rutas locales; no recibe token, URL ni headers GitHub. La integración CTN se acepta mediante la prueba coordinada; los tests locales no acreditan un despliegue OCI.

## Manifiesto del producto

Ambas fases declaran `release_assets: [{name,max_bytes,download}]` en `terraform/deploy-studio.json`. Preflight descarga tres JSON y solo consulta metadata de los tres gzip. Post-apply descarga los seis. Cada JSON permite 65.536 bytes; límites gzip API 512 MiB, visor 1 GiB, gateway 128 MiB. No cuentan contra el límite de extracción de fuentes de 10 MiB.

| Componente | JSON | Gzip |
| --- | --- | --- |
| api | `gods-eye-view-api-release.json` | `gods-eye-view-api-image-amd64.tar.gz` |
| viewer | `gods-eye-view-release.json` | `gods-eye-view-image-amd64.tar.gz` |
| gateway | `gods-eye-view-gateway-release.json` | `gods-eye-view-gateway-image-amd64.tar.gz` |

## Contexto confiable del runner

Contrato indicado por el coordinador; requiere la versión CTN que lo implementa:

```json
{
  "release_assets": {
    "schema_version": 1,
    "repository": "https://github.com/jgangini/aidp-ai-gods-eye-view",
    "ref": "v1.0.0",
    "commit_sha": "<commit de 40 hex>",
    "release_id": 123,
    "assets": {
      "gods-eye-view-api-release.json": {
        "asset_id": 456,
        "size": 564,
        "sha256": "<64 hex>",
        "path": "<ruta local absoluta readonly>"
      }
    }
  }
}
```

El ejemplo abrevia los seis assets; IDs/tamaños/rutas son ilustrativos. El runner verifica repositorio/ref/SHA fijados, release estable inmutable y metadata GitHub exacta. El campo no procede del formulario. `path` existe solo para archivos descargados y verificados, en el área aislada del job. El consumidor requiere los seis nombres exactos, IDs positivos distintos, límites/tamaños/hashes válidos y bindings coincidentes con `context.source.repository/commit_sha` y `inputs.release_tag/source_commit_sha`.

`inspect_handoff(context)` revalida los JSON y sus hashes, la identidad semántica de los tres manifests y metadata de gzip. `inspect_handoff(context, require_archives=True)` exige además archivos gzip locales y comprueba todos sus bytes antes de iniciar la instalación. `stage_handoff(context, storage)` repite la validación antes de publicar objetos CAS: no sobrescribe conflictos y comprueba todos los componentes antes del primer upload. Se rechazan directorios, rutas relativas y symlinks. Ausencia o invalidez del contexto falla antes del journal y mutaciones nativas.

Cada manifiesto schema 1/updater_protocol 1 vincula `repository`, `release`, `commit_sha`, `image.asset_name`, `image.sha256`, `image.platform=linux/amd64`, `image.image_tag` y `image.image_id`. El downloader HTTP anterior permanece aislado/probado, pero no es llamado por los hooks activos.

## Entrega OCI y VM

El resultado interno usa exactamente tres descriptores:

```json
{
  "component": "api",
  "object_name": "releases/<commit>/gods-eye-view-api-image-amd64.tar.gz",
  "archive_sha256": "<64 hex>",
  "image_id": "sha256:<64 hex>",
  "image_tag": "gods-eye-view-api:<commit>"
}
```

Viewer/gateway usan sus prefijos de la tabla. Namespace y bucket proceden de outputs Terraform verificados. La VM descarga mediante instance principal restringido, verifica SHA antes de `docker load`, comprueba ID/plataforma y usa imágenes locales con `pull_policy: never`. Sin token GitHub/registry ni URL bearer.

`vm-bootstrap.zip` es un artifact separado de cuatro archivos del mismo código; no forma parte de los seis assets de imagen. Preflight deriva objeto y hash del código fijado y los entrega como `vm_bundle_object`/`vm_bundle_sha256`, sin campos manuales. Post-apply valida/publica el bundle en el bucket operativo seleccionado. Una release estable inmutable tiene exactamente seis assets; los artifacts CI `release=candidate` se rechazan como release instalable.

## Parámetros de la prueba compartida

- Orden Governance→Market→GodEye sobre un AIDP. Para GodEye: `aidp_mode=existing`, `existing_ai_data_platform_ocid` y `existing_workspace_key` iguales a los outputs exactos de la primera instalación. No crear otra plataforma. Aún no se conocen esos valores reales en este candidato.
- `identity_domain_id`: selección `oci_identity_domains` con valor OCID, dominio ACTIVE; `admin_user_ocid`: usuario ACTIVE de ese dominio, seleccionado por `oci_aidp_administrators` y revalidado con roles efectivos USER/GROUP/ROLE. Operador firmante separado del administrador elegido.
- `existing_catalog_key`: clave exacta al reutilizar `oci_medallion`; ausencia permite creación administrada. Resume rechaza cambiar catálogo, workspace, plataforma o administrador.
- Cinco buckets distintos: `landing_bucket_name`, `bronze_bucket_name`, `silver_bucket_name`, `gold_bucket_name`, `artifacts_bucket_name`. `create_buckets=false` al reutilizarlos. Mantener región y namespace correctos.
- `agent_model_id` sigue siendo una selección del despliegue. Preflight resuelve `availability_domain` e `image_ocid` Oracle Linux 9 y calcula objeto/SHA del bundle. Terraform deriva `public_origin` de la IP asignada; la VM genera TLS local. No hay campos manuales de dominio, certificado, clave TLS ni bundle. `source_commit_sha` deriva de la fuente confiable del runner. `release_tag` debe identificar la release estable del código validado.

El coordinador posee Browser/Docker compartido, colas, exclusión mutua y mutaciones OCI. Mantener privado. Preparar/publicar assets no demuestra APPLY, bootstrap, task/publicación ni conversación real; no se ejecutan actores pagados ni una evaluación ampliada de respuestas.


Release disponible: `v1.0.0`, SHA `219014036e3fbba1d808f5f10822aa786bf607f6`, privada e inmutable, ID `436010655`. [Recibo con los seis assets reales y bundle separado](releases/v1.0.0.json). El catálogo CTN aún debe habilitar este proyecto; no se alteró desde esta tarea.

Parche vigente: [`v1.0.1`](https://github.com/jgangini/aidp-ai-gods-eye-view/releases/tag/v1.0.1), SHA `6605611c02ea79f1732044ea8305b8b6da322ed8`, ID `436036581`, privada e inmutable. [Recibo completo](releases/v1.0.1.json). Corrige el primer arranque sin dominio/certificado ni bundle manuales. VM local TLS y revisión del host documentadas en [operación](operations.md). v1.0.0 se conserva; no se alteraron sus assets.

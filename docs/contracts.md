# Instalación e identidad

God’s Eye View se instala mediante Deploy Studio. Su [manifiesto](../terraform/deploy-studio.json) define el proyecto `aidp-ai-gods-eye-view`; el identificador de producto es `gods_eye_view`. El repositorio y las releases de aplicación son públicos. Los datos, claves y objetos operativos de cada instalación permanecen en su entorno OCI.

## Requisitos

- Cuenta OCI y operador autorizado para los recursos del plan, Identity Domains, AIDP, Object Storage y Compute Instance Run Command.
- Región suscrita compatible con AIDP y GenAI Chat, con capacidad para una VM Standard E5 Flex de 2 OCPU y 16 GiB.
- Identity Domain ACTIVE y administrador ACTIVE de ese dominio. En una plataforma existente, operador y administrador deben superar la comprobación de permisos AIDP efectivos.
- Cinco buckets distintos para Landing, Bronze, Silver, Gold y artifacts: crearlos en este despliegue o disponer de ellos con permisos adecuados.
- Modelo OCI seleccionado mediante `agent_model_id` y salida de la VM hacia repositorios de paquetes, Identity Domains, OCI y los proveedores configurados.

La selección de imagen/shape no reserva capacidad. El lanzamiento efectivo y la propagación IAM deben comprobarse en OCI.

## Instalar una plataforma nueva

1. En Deploy Studio, seleccionar este proyecto, una release estable `vMAJOR.MINOR.PATCH` como fuente y el mismo valor en `release_tag`.
2. Elegir región y compartimento. Seleccionar Identity Domain y administrador desde sus listas; el valor persistido es su OCID.
3. Elegir `aidp_mode=new`, un prefijo de recursos estable, el modelo y las cinco selecciones de buckets.
4. Revisar el plan y ejecutar el despliegue. El operador conserva su propia identidad firmante. Post-apply concede/verifica `AI_DATA_PLATFORM_ADMIN` para el administrador seleccionado y añade su acceso al grupo lector del visor.
5. Revisar los outputs, la salud y el estado nativo. Establecer confianza en el certificado publicado por Deploy Studio antes de iniciar OIDC en el visor.

La creación de compartimento y la elección new/existing de AIDP son decisiones distintas.

## Usar AIDP existente

Elegir `aidp_mode=existing` y proporcionar `existing_ai_data_platform_ocid` y `existing_workspace_key` exactos. El hook comprueba plataforma/workspace activos, permisos del operador y roles efectivos del administrador. Terraform la consulta como data source; no la convierte en un recurso administrado por esta instalación.

Para reutilizar un catálogo externo, indicar `existing_catalog_key` exacto. Preflight verifica que corresponda a `oci_medallion` de tipo `INTERNAL`; un nombre coincidente no permite adoptarlo. Si ya existe ese nombre sin clave exacta ni recibo propio verificable, la validación bloquea antes de APPLY. Resume puede recuperar la clave del recibo de esta misma instalación, tras comprobar deployment, plataforma, administrador, dominio y operador; esa consulta solo lee el recibo. Si no existe el catálogo, la instalación puede crearlo y registrar su identidad. Al reutilizar buckets, usar `create_buckets=false`.

Para compartir una plataforma con [AIDP AI Data Governance](https://github.com/jgangini/aidp-ai-data-gobernance) u otros módulos, conservar sus OCID, workspace, región y selecciones de almacenamiento verificadas. No crear otra plataforma como sustitución de una instalación existente.

## Parámetros del formulario

| Parámetro | Uso |
| --- | --- |
| `identity_domain_id` | Selector `oci_identity_domains`: valor OCID; contrato CTN de dominios ACTIVE en región home, etiqueta con nombre/compartimento. |
| `admin_user_ocid` | Selector `oci_aidp_administrators`; revalidación en el hook, incluidos USER, GROUP y ROLE heredados. |
| `aidp_mode` | `new` o `existing`. |
| `existing_ai_data_platform_ocid`, `existing_workspace_key` | Obligatorios para AIDP existente. |
| `existing_catalog_key` | Clave exacta del catálogo externo, si se reutiliza. |
| `name` | Prefijo estable de recursos. |
| `create_buckets` | Crear las cinco selecciones o usar buckets existentes. |
| `landing_bucket_name`, `bronze_bucket_name`, `silver_bucket_name`, `gold_bucket_name`, `artifacts_bucket_name` | Cinco nombres distintos. |
| `agent_model_id` | Modelo OCI para el agente. |
| `release_tag` | Misma release estable e inmutable que la fuente seleccionada. |

El runner fija `source_commit_sha`. Preflight obtiene endpoint del dominio, región home, identidad/fingerprint del operador, imagen Oracle Linux 9 y AD compatibles, y objeto/hash del bundle. Conserva la imagen y el AD ya fijados al reanudar. Esos valores no se descubren ni escriben manualmente en el formulario.

Terraform deriva `public_origin` de la IP pública asignada y registra ese mismo origen en el callback OIDC. No exige dominio DNS, certificado, clave TLS ni coordenadas del bundle aportadas por el usuario.

## Acceso al visor

La entrada es `/gods-eye-view/`; los administradores abren `/controls/` dentro del visor. Solo el gateway publica TLS 443. API, bridge y Node permanecen en la red interna.

OIDC utiliza `/api/auth/oci/callback`, PKCE, firma, issuer, audience, nonce y vigencia. El gateway elimina headers de identidad externos. `/api/gods-eye-view/session` revalida cuenta y membresía; `/api/admin/session` exige además el administrador seleccionado y permisos AIDP efectivos. La selección administrativa no suplanta al operador OCI. No hay registro/login local ni instalación HTTP.

La API se despliega con un solo worker. Las transacciones OIDC y sus límites son por proceso; usar varios workers o instancias requiere almacenamiento compartido y validación del escalado.

## Credenciales, TLS y persistencia

El control plane entrega [assets verificados](private-artifact-handoff.md). El hook vuelve a comprobar repositorio/ref/SHA, manifiestos y bytes; la VM carga imágenes por ID local con `pull_policy: never`. Ningún token GitHub/registro llega al hook o a la VM.

Perfil y clave OCI se entregan en un sobre RSA/AES-GCM ligado a deployment, operador y fingerprint. El receptor comprueba la clave/perfil, escribe archivos atómicos y consume la clave temporal. El objeto de entrega se elimina con ETag y se verifica su ausencia. Nunca incluir `.oci`, claves o estado en Git o imágenes.

La VM genera su clave TLS RSA 3072 y una hoja autofirmada anual con SAN de su IP. OCI Run Command devuelve solo certificado público canónico y huella SHA-256 DER. El hook verifica salud confiando exclusivamente en esa hoja y comprobando IP/vigencia, sin proxy ambiental. **El navegador requiere confianza explícita en ese certificado/IP; no es una CA pública.** Véanse [operación y recuperación](operations.md).

Object Storage, Gold, checkpoints y recibos conservan el estado durable. SQLite y cachés son proyecciones reconstruibles. `aidp/manifest.json` declara tres programas, sus fuentes/hashes y recursos nativos; publicación y consultas conservan la relación `publication_version`.

## Verificación de una instalación

Un post-apply satisfactorio comprueba task/publicación, recibo de imágenes y salud TLS, incluida respuesta 401 para sesión anónima. Devuelve `installed_conversation_pending`: no acredita una conversación del agente. Permisos negativos, confianza Browser y comportamiento nativo necesitan aceptación en el entorno real. Las pruebas locales y los mocks no sustituyen esa aceptación.

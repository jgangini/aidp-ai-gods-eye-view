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

1. En Deploy Studio, seleccionar este proyecto y una release estable `vMAJOR.MINOR.PATCH` como fuente. El hook obtiene `release_tag` de esa referencia inmutable; no se introduce otro tag en el formulario.
2. Elegir región y compartimento. Seleccionar Identity Domain y administrador desde sus listas; el valor persistido es su OCID.
3. Elegir `aidp_mode=new`, el nombre del AIDP nuevo, el modelo y las cinco selecciones de buckets.
4. Revisar el plan y ejecutar el despliegue. El operador conserva su propia identidad firmante. Post-apply concede/verifica `AI_DATA_PLATFORM_ADMIN` para el administrador seleccionado y añade su acceso al grupo lector del visor.
5. Revisar los outputs, la salud y el estado nativo. Establecer confianza en el certificado publicado por Deploy Studio antes de iniciar OIDC en el visor.

La creación de compartimento y la elección new/existing de AIDP son decisiones distintas.

## Usar AIDP existente

Elegir `aidp_mode=existing` y proporcionar `existing_ai_data_platform_ocid` y `existing_workspace_key` exactos. El hook comprueba plataforma/workspace activos, permisos del operador y roles efectivos del administrador. Terraform la consulta como data source; no la convierte en un recurso administrado por esta instalación.

Para reutilizar un catálogo externo, indicar `existing_catalog_key` exacto. Preflight verifica que corresponda a `oci_medallion` de tipo `INTERNAL`; un nombre coincidente no permite adoptarlo. Si ya existe ese nombre sin clave exacta ni recibo propio verificable, la validación bloquea antes de APPLY. Resume puede recuperar la clave del recibo de esta misma instalación, tras comprobar deployment, plataforma, administrador, dominio y operador; esa consulta solo lee el recibo. Si no existe el catálogo, la instalación puede crearlo y registrar su identidad. Para cada bucket reutilizado, seleccionar su modo existing y su identidad exacta mediante el selector OCI.

Para compartir una plataforma con [AIDP AI Data Governance](https://github.com/jgangini/aidp-ai-data-gobernance) u otros módulos, conservar sus OCID, workspace, región y selecciones de almacenamiento verificadas. No crear otra plataforma como sustitución de una instalación existente.

## Parámetros del formulario

| Parámetro | Uso |
| --- | --- |
| `identity_domain_id` | Selector `oci_identity_domains`: valor OCID; contrato CTN de dominios ACTIVE en región home, etiqueta con nombre/compartimento. |
| `admin_user_ocid` | Selector `oci_aidp_administrators`; revalidación en el hook, incluidos USER, GROUP y ROLE heredados. |
| `aidp_mode` | `new` o `existing`. |
| `existing_ai_data_platform_ocid`, `existing_workspace_key` | Obligatorios para AIDP existente. |
| `existing_catalog_key` | Clave exacta del catálogo externo, si se reutiliza. |
| `new_aidp_name` | Nombre visible del AIDP nuevo; default `aidp_gods_eye_view`. Solo aparece en modo new. No cambia el nombre del workspace ni los recursos del visor. |
| `name` (interno) | Prefijo de infraestructura, oculto. Preflight conserva el valor de una instalación al reanudar o usa `aidp-gods-eye-view`. |
| `artifacts_mode` | Crear o reutilizar solo el bucket de Artifacts. Default new. |
| `artifacts_bucket_name`, `artifacts_existing_bucket_name` | Textbox de nombre nuevo o selector `oci_active_buckets`, según modo. Default `oci_artifacts`. |
| `<layer>_bucket_mode` | Modo new/existing independiente para Landing, Bronze, Silver y Gold. |
| `<layer>_new_bucket_name`, `<layer>_existing_bucket_name` | Textbox de nombre nuevo o selector OCI por capa. Defaults `oci_landing`, `oci_bronze`, `oci_silver`, `oci_gold`. |
| `bucket_modes` (interno) | JSON obligatorio con los cinco modos exactos; sustituye al control global anterior, sin fallback. |
| `agent_model_id` | Selector `oci_genai_chat_models` para el modelo OCI del agente. |
| `release_tag` (interno) | Derivado de la ref estable de la fuente; una selección diferente se rechaza. |

Los grupos siguen el orden de Governance: credenciales, servicios OCI, Identity, AI Data Platform Workbench, Agent Flow, Artifacts, Medallion Architecture y recursos AIDP adicionales. Las cuatro filas Medallion siguen el patrón de Kits: modo a la izquierda y nombre nuevo o selector existente a la derecha. Plataforma y workspace existentes utilizan los selectores `oci_aidp_platforms` y `oci_aidp_workspaces`, visibles solo en modo existing. El catálogo externo conserva su clave exacta opcional para ese modo. El formulario declara la imagen local compartida de CTN y el enlace al proyecto original.

Los cinco nombres deben ser distintos. Cada bucket existing se consulta en el cliente de la región seleccionada, sin redirecciones a otras regiones, y debe pertenecer al compartimento del despliegue. Reutilizar buckets con un compartimento aún no creado se rechaza antes de APPLY. No se amplían las políticas al tenancy. Terraform crea solo las claves en modo new y conserva las direcciones `product[landing|bronze|silver|gold|artifacts]` y `prevent_destroy`. Post-apply compara nombres y modos con los outputs Terraform antes de escribir el journal y vuelve a comprobar la ubicación de los existentes.

El runner fija `source_commit_sha`. Preflight obtiene endpoint del dominio, región home, identidad/fingerprint del operador, prefijo de infraestructura, imagen Oracle Linux 9 y AD compatibles, y objeto/hash del bundle. Conserva el prefijo, la imagen y el AD ya fijados al reanudar. Esos valores no se descubren ni escriben manualmente en el formulario.

Terraform deriva `public_origin` de la IP pública asignada y registra ese mismo origen en el callback OIDC. No exige dominio DNS, certificado, clave TLS ni coordenadas del bundle aportadas por el usuario.

## Acceso al visor

La entrada es `/gods-eye-view/`; los administradores abren `/controls/` dentro del visor. Solo el gateway publica TLS 443. API, bridge y Node permanecen en la red interna.

OIDC utiliza `/api/auth/oci/callback`, PKCE, firma, issuer, audience, nonce y vigencia. El gateway elimina headers de identidad externos. `/api/gods-eye-view/session` revalida cuenta y membresía; `/api/admin/session` exige además el administrador seleccionado y permisos AIDP efectivos. La selección administrativa no suplanta al operador OCI. No hay registro/login local ni instalación HTTP.

El administrador entra con la cuenta OCI seleccionada del Identity Domain; su contraseña se gestiona en ese dominio, no mediante campos de aplicación en Deploy Studio. La VM se administra por OCI Compute Instance Run Command. El formulario no declara un Username/Password local, y Terraform no configura credenciales SSH ni una regla de entrada 22.

La API se despliega con un solo worker. Las transacciones OIDC y sus límites son por proceso; usar varios workers o instancias requiere almacenamiento compartido y validación del escalado.

## Credenciales, TLS y persistencia

El control plane entrega [assets verificados](private-artifact-handoff.md). El hook vuelve a comprobar repositorio/ref/SHA, manifiestos y bytes; la VM carga imágenes por ID local con `pull_policy: never`. Ningún token GitHub/registro llega al hook o a la VM.

Perfil y clave OCI se entregan en un sobre RSA/AES-GCM ligado a deployment, operador y fingerprint. El receptor comprueba la clave/perfil, escribe archivos atómicos y consume la clave temporal. El objeto de entrega se elimina con ETag y se verifica su ausencia. Nunca incluir `.oci`, claves o estado en Git o imágenes.

La VM genera su clave TLS RSA 3072 y una hoja autofirmada anual con SAN de su IP. OCI Run Command devuelve solo certificado público canónico y huella SHA-256 DER. El hook verifica salud confiando exclusivamente en esa hoja y comprobando IP/vigencia, sin proxy ambiental. **El navegador requiere confianza explícita en ese certificado/IP; no es una CA pública.** Véanse [operación y recuperación](operations.md).

Object Storage, Gold, checkpoints y recibos conservan el estado durable. SQLite y cachés son proyecciones reconstruibles. `aidp/manifest.json` declara tres programas, sus fuentes/hashes y recursos nativos; publicación y consultas conservan la relación `publication_version`.

## Verificación de una instalación

Un post-apply satisfactorio comprueba task/publicación, recibo de imágenes y salud TLS, incluida respuesta 401 para sesión anónima. Devuelve `installed_conversation_pending`: no acredita una conversación del agente. Permisos negativos, confianza Browser y comportamiento nativo necesitan aceptación en el entorno real. Las pruebas locales y los mocks no sustituyen esa aceptación.

## Formulario declarativo de Deploy Studio

`terraform/deploy-studio.json` utiliza `schema_version: 2`. `form.groups` declara los títulos y el orden de los grupos; cada lista `items` fija el orden de campos, archivos y controles comunes, y `span` su ancho en columnas. Región ocupa una fila completa con `span: 2`, seguida del modo y nombre del compartimento. Los campos declaran valores predeterminados y condiciones de visibilidad. CloudTechNext valida las referencias y requiere este contrato; no reconstruye formularios antiguos. Las credenciales se cargan en el grupo `credentials`; los demás controles se habilitan tras validarlas. Las releases publicadas conservan sus manifiestos inmutables: este contrato requiere una nueva release y un motor compatible.

El manifiesto declara `execution_source: "oci_resource_manager"`. `run_steps` define únicamente las etiquetas y el orden de las fases del ciclo de despliegue, como cola, credenciales, PLAN, APPLY y finalización; cada producto declara las fases que presenta. No define el inventario ni el orden de creación de recursos. Deploy Studio obtiene ese inventario del PLAN de OCI Resource Manager y actualiza las filas de recursos dentro de APPLY con sus logs reales; Terraform puede ejecutar recursos en paralelo según sus dependencias. La fase `application` conserva la verificación de AIDP y del visor que ejecuta el hook posterior a APPLY; el éxito de Terraform no acredita esa verificación.

## Etiquetas de recursos en Deploy Studio

El output no sensible `deploy_studio_resource_labels` relaciona cada dirección exacta de instancia Terraform con una etiqueta breve en inglés. Se resuelve durante PLAN, incluye las instancias seleccionadas de recursos y consultas de datos y omite las que tienen `count = 0`. Las claves de `for_each` conservan su representación JSON entre corchetes. Las etiquetas no contienen OCID, credenciales ni atributos calculados. CloudTechNext puede mostrar estos nombres y conservar la dirección en los detalles técnicos; el inventario, las acciones, el progreso y las dependencias proceden del PLAN y los logs de OCI Resource Manager, no de este mapa ni del orden de los archivos `.tf`.

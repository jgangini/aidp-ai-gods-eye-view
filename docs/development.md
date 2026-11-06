# Desarrollo y validación

El código editable y sus consumidores definen el comportamiento del producto. Los [contratos](contracts.md) mantienen las interfaces e identidades; la [operación](operations.md) define recuperación y límites de instalación; el [contrato de release](release-contract.md) y el [handoff de assets](private-artifact-handoff.md) definen la entrega. No crear un segundo contrato o un flujo de validación paralelo para una modificación.

## Herramientas y preparación

Utilizar Python 3.12, Node 24.14.0 y Terraform 1.15.7 para reproducir el entorno de CI. El proveedor OCI está fijado a 8.28.0 en `terraform/a_versions.tf` y se conserva el lock de proveedores. PowerShell ejecuta los wrappers locales; Bash se utiliza para la regresión del bootstrap. Los tests de Nginx requieren una ejecución Linux con el binario disponible.

Instalar dependencias en un entorno propio, sin reutilizar `node_modules` ni una venv de otro repositorio. Ejemplo PowerShell para un checkout nuevo:

```powershell
py -3.12 -m venv .venv
./.venv/Scripts/python.exe -m pip install -r apps/backend/requirements-dev.txt
npm ci --ignore-scripts --prefix apps/frontend
./.venv/Scripts/python.exe modules/ai-gods-eye-view/prepare_upstream.py --output modules/ai-gods-eye-view/.upstream
npm ci --ignore-scripts --prefix modules/ai-gods-eye-view/.upstream
terraform -chdir=terraform init -backend=false -input=false
```

El preparador exige un directorio `.upstream` inexistente o vacío. Si ya existe una preparación, conservarla y comprobar su procedencia; para otra revisión, materializar en un directorio nuevo conforme a la [guía del visor](../modules/ai-gods-eye-view/README.md). No editar el árbol generado ni borrar estado para hacer pasar un hash. El preparador comprueba el archivo fuente y cada parche; Docker reproduce esa preparación sin depender del árbol local.

Mantener `.oci`, `.local`, `.venv`, `node_modules`, `.upstream`, Terraform state, claves y archivos de entorno fuera de Git y del contexto de imágenes. No copiar credenciales de desarrollo a un bundle ni a una imagen. El build y las pruebas locales no requieren inferencia, actores pagados ni mutaciones OCI.

## Ruta de validación

Antes de un cambio no trivial de código, configuración o estructura, ejecutar `scripts/arch-preflight.ps1`. Tras la edición final, ejecutar `scripts/arch-postflight.ps1`. El postflight llama a `scripts/test.ps1`, que utiliza la venv local y delega en `scripts/check_product.py`; no volver a ejecutar esa misma suite completa por otra vía para contabilizarla dos veces.

`scripts/check_product.py` valida la selección explícita de suites Python, los tests de `tests/` y `terraform/tests/`, el renderizado de los programas AIDP y los checks Terraform de formato, validación y mocks. Su opción `--backend-only` omite los comandos Terraform y se usa en CI, donde Terraform tiene un job separado. Los tests Python de contratos Terraform siguen incluidos en esa selección.

Los hooks respetan ambos contextos de CloudTechNext: preflight recibe `compartment` como string y `compartment_mode=new|existing`; post-apply recibe un objeto con `id` y `name`, sin mode. Antes de crear un compartimento, la consulta de compatibilidad Compute utiliza la tenancy; con uno existente utiliza su OCID. Post-apply exige que el ID coincida con `terraform_outputs.compartment_ocid` y rechaza contextos malformados.

El runner filtra Terraform state mediante `manifest.outputs` antes del hook. El manifiesto declara los 15 outputs Terraform no sensibles consumidos por la instalación y los seis derivados del hook; no presupone acceso al resto del state. `tests/test_runner_outputs.py` prueba esa proyección, ambos modos de workspace y la configuración nativa. Cuando existe un checkout hermano de CloudTechNext o `CLOUDTECHNEXT_SOURCE_ROOT`, también ejecuta su parser y proyección reales sin inicializar servicios; ese check externo es opcional en CI.

Los controles React y el visor nativo tienen sus propios runners existentes. Ejecutar los checks afectados por el cambio y conservar los resultados de la revisión final:

| Superficie | Comandos existentes |
| --- | --- |
| Controles React | `npm test --prefix apps/frontend` y `npm run build --prefix apps/frontend`. |
| Visor nativo | `node --test modules/ai-gods-eye-view/tests/*.test.mjs` y `node modules/ai-gods-eye-view/native/runtime.mjs --build`. Utilizan las dependencias fijadas de `.upstream`. |
| Bootstrap y rollback Compose | `bash docker/tests/bootstrap-rollback.sh`, con fixtures y comandos Docker simulados. |
| Python, AIDP generado y Terraform | `scripts/arch-postflight.ps1`, mediante la ruta única descrita arriba. |

`npm run build` en el directorio raíz del visor construye la página standalone conservada para revisión y pruebas. No sustituye el build de la aplicación nativa desplegada. Un test de fixtures, un build o un mock Terraform no equivalen a aceptación del runtime OCI.

Los temporales pytest deben ser directorios nuevos bajo `.local`; pytest puede limpiar un `--basetemp` ya existente. `check_product.py` genera un nombre UUID nuevo para cada ejecución. En Windows, un bloqueo de ACL o de procesos hijos puede requerir la escalación de sandbox correspondiente; conservar el fallo y la repetición autorizada como evidencias distintas, sin borrar corridas anteriores ni cambiar assertions para eludir permisos.

Una modificación exclusivamente documental no requiere repetir suites funcionales ni checks de arquitectura, salvo que modifique reglas de arquitectura o grafos. Verificar el texto, sus referencias al código, los enlaces locales y `git diff --check` en los archivos editados.

## Alcance explícito de las suites

`apps/backend/tests/validation-scope.json` es el inventario de selección. `product_suites()` exige que cada suite de ese directorio esté clasificada exactamente como gate de producto o como fuente retenida fuera de ese contrato. Si se añade o se retira una suite, actualizar su clasificación y explicar el comportamiento cubierto.

Las suites retenidas del instalador combinado comprueban el protocolo del portal anterior; no forman parte de la aplicación independiente ni de su gate. El inventario indica sus sustitutos de instalación, permisos y streaming. Conservarlas como evidencia no acredita que pasen; tampoco permite excluir fallos de una suite que sí pertenece al producto. No declarar aprobada toda la suite histórica a partir de una selección curada.

Separar las pruebas de fábrica y fixtures de las comprobaciones de tareas nativas, publicación Gold/Object, permisos y conversación del agente. Un skip debe conservar su motivo y el entorno que falta; no contarlo como aprobado. Los resultados concretos de validación pertenecen a la evidencia de la revisión, no a una promesa permanente de esta guía.

## Arquitectura y baseline Sentrux

La ruta de arquitectura utiliza la CLI Sentrux desde los wrappers. Preflight compara contra `.sentrux/baseline.json` cuando existe; si falta, guarda la referencia del checkout. Postflight vuelve a ejecutar el gate y comprueba reglas si están configuradas. No cambiar un baseline existente, reducir el alcance ni sobrescribir resultados para convertirlo en verde.

Conservar el resultado, identificar el baseline usado, revisar las regresiones concretas y documentar la decisión de ingeniería sobre diferencias aceptadas. Una referencia de otro alcance puede ayudar a interpretar una señal, pero no reemplaza el baseline ni permite ocultar un error. La [evidencia de validación](tasks/current.md) incluye un gate no aprobado frente a una referencia inicial vacía; no asumir aprobación de arquitectura a partir de CI o de checks funcionales. La conclusión debe distinguir checks aprobados, arquitectura degradada y limitaciones sin resolver.

No hay reglas Sentrux propias ni un grafo Graphify configurado. Informar esa ausencia. No inicializar un grafo como efecto secundario de una edición; el postflight solo actualiza uno si ya existe. Arko guía responsabilidades, contratos y consumidores, pero su perfil CLI no valida directamente el layout de módulos conservado: no declarar `arko check` aprobado sin una adaptación explícita y comprobada.

## Builds y entrega

CI separa Python, Terraform, controles/visor y las tres imágenes del producto. Los jobs de imágenes construyen API, visor y gateway y utilizan `scripts/release/package_candidate.py` para empaquetar los bytes locales con gzip determinista y sus manifiestos. No se trata de una publicación de release ni de un despliegue. Los artifacts `candidate` no superan el gate de release estable e inmutable.

El repositorio público y sus assets de release no requieren trasladar tokens privados a los hooks o a la VM. Deploy Studio entrega un contexto confiable con la misma referencia y SHA de fuente, los seis nombres exactos y metadata/rutas locales; los hooks revalidan los manifiestos y bytes antes de publicar objetos OCI. La VM verifica el archivo antes de cargarlo y después comprueba ID y plataforma, utilizando IDs locales y `pull_policy: never`. Consultar el [contrato de entrega](private-artifact-handoff.md) para los límites de tamaño, fases y responsabilidades del runner.

Los cambios del bundle o de `user_data.sh` cambian la revisión del host. No dar por hecho que una actualización de imágenes actualiza esos scripts: el protocolo V2 exige coincidencia y deriva a recuperación explícita cuando difiere. Mantener los checks de Resume, recepción idempotente, recibos de imágenes activas y rollback de configuración asociados al comportamiento que se modifica.

Antes de publicar código o assets, utilizar el escáner existente `scripts/scan_secrets.py`, revisar `git diff --check` y los paths seleccionados. El escáner imprime paths/reglas, no valores; detecta patrones y no demuestra la ausencia de todo secreto posible. No leer ni listar `.oci` para completar esa revisión. Mantener outputs privados de instalación y credenciales separados de la documentación pública.

La aceptación de Deploy Studio en su entorno real, de IAM/roles, capacidad VM, confianza TLS en navegador y tareas/publicaciones/conversación AIDP debe comprobarse por separado. No presentarla como realizada por haber superado las pruebas locales o CI.

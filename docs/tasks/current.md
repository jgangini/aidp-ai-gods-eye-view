# Candidato de migración God’s Eye View

Estado actual: corrección del primer arranque v1.0.1 en validación. El origen y OIDC derivan de la IP asignada; preflight resuelve imagen/AD y objeto/hash del bundle. La VM genera TLS local y publica solo certificado/huella. Las evidencias de v1.0.0 indicadas abajo son históricas; esa release inmutable se conserva.

Estado: candidato local validado y publicado en el repositorio privado. El consumidor del handoff privado está implementado. La release privada inmutable `v1.0.0` está publicada con seis assets verificados. Integración CTN y aceptación OCI pendientes; no se hicieron mutaciones OCI.

## Repositorio y alcance

- Destino: `D:/dev/codex-aidp-ai-gods-eye-view`.
- Remoto privado: `https://github.com/jgangini/aidp-ai-gods-eye-view`; permiso ADMIN verificado. No se cambió su visibilidad.
- Código validado y tag `v1.0.0`: `219014036e3fbba1d808f5f10822aa786bf607f6`. Los commits posteriores de cierre documental no cambian ese código. [Release privada inmutable](https://github.com/jgangini/aidp-ai-gods-eye-view/releases/tag/v1.0.0), ID `436010655`, seis assets exactos, sin draft/prerelease; [recibo con tamaños y SHA](../releases/v1.0.0.json).
- Fuente congelada: `3c82617fd298933995e954955841007253cc0985`. Extracción de 417 archivos versionados, con procedencia y hashes; sin `.oci`, estado ni caches.
- Requisitos: [diagnóstico](../migration-assessment.md) y contrato de separación del coordinador. Única interfaz integrada al visor; instalación por Deploy Studio.

## Implementación

API propia `app.main:create_app`, OIDC, membresía/revocación y RBAC por OCID y roles AIDP directos, grupos y roles heredados. Controles social/sensor/proveedores integrados al visor upstream fijado. Los programas AIDP conservan Gold, Object Storage, CAS, checkpoints y cuatro computes separados. El usuario lector necesita membresía actual; administrar requiere además el administrador seleccionado y su rol efectivo vigente.

Terraform implementa AIDP new/existing con recursos externos fuera del state administrado. Hooks verifican identidad y administrador, registran recursos exactos y rechazan adopción por nombre o cambio de plataforma/workspace/catalog al reanudar. El bundle VM es determinista y se verifica por SHA. La entrega del operador OCI está cifrada y ligada al operador, fingerprint y deployment. Seleccionar administrador no suplanta al firmante. Compose publica solo el gateway TLS y usa imágenes locales por ID inmutable. Updates rechazan rotación implícita de credenciales OCI o TLS.

El consumidor local del handoff valida contexto, repositorio/ref/SHA, seis assets, manifiestos y bytes antes de mutar recursos; usa snapshots verificados y CAS. El descargador HTTP aislado conserva sus tests, pero no es llamado por los hooks. El consumidor VM verifica bytes, ID y plataforma. El manifiesto activo no pide un token GitHub ni supone `GH_TOKEN`/`GITHUB_TOKEN` en hooks. Preflight y post-apply rechazan el prerequisito ausente antes de mutar recursos. El [contrato mínimo de handoff](../private-artifact-handoff.md) distingue implementación actual y adaptación pendiente.

## Evidencia histórica del código v1.0.0

- Preflight: baseline Sentrux guardado antes de extraer código, con 5 archivos y calidad 7780. Sin reglas propias ni grafo Graphify.
- Postflight `scripts/arch-postflight.ps1` sobre el código de handoff: **1625 passed, 6 skipped**, tres programas y tres manifests de fuentes AIDP verificados, Terraform validate y dos escenarios mock new/existing aprobados. El comando completo termina con error por el gate Sentrux descrito abajo.
- [CI 42147141832](https://github.com/jgangini/aidp-ai-gods-eye-view/actions/runs/42147141832): seis jobs aprobados sobre ese SHA: Python, Terraform, frontend y builds/paquetes de las imágenes API, visor y gateway. Los dos CI anteriores de integración también aprobaron. Se corrigieron las dos causas del primer CI fallido; no se rebajaron assertions.
- Frontend: 89 tests y build React aprobados. Visor: 119 tests nativos y build de 753 módulos aprobados con Node 24.14.0. Puente: 143 tests aprobados. Los lotes focalizados se solapan con el postflight y no se suman como cobertura distinta.
- Nginx real Linux: autorización, outage y passthrough aprobados en contenedor existente, sin red y con mounts explícitos readonly. Rollback del script probado con Docker simulado: restaura configuración e imágenes del mismo recibo y conserva puntero/checksums.
- API Docker construida desde base local existente; smoke sin red/puertos aprobado: health, rechazo anónimo, ausencia de endpoint deploy y exclusión de código histórico/evaluación. Pydantic de producción alineado con la versión probada.
- Parser Pydantic y extractor **reales** de Deploy Studio, sobre el ZIP completo del commit/tag `21901403`: **46.595.480 bytes** de archivo; **87 archivos / 1.138.957 bytes** seleccionados. Límites reales de Settings: 100 MiB de archivo GitHub, 250 archivos y 10 MiB extraídos. No se ampliaron.
- En la imagen existente de CTN, sin red y montando solo esos 87 archivos: imports de ambos hooks aprobados; `build_vm_bundle.build()` produce **16.995 bytes**, SHA-256 `f69991224a04364c8929107ca3895c8b8228ea3f141379d9adbb2f55c29a24b8`, igual al bundle CI. Sin dependencias accidentales del árbol completo.
- CI produjo tres archivos de imagen y tres manifiestos `release=candidate`, más un bundle VM separado. Se promovió únicamente el campo release de los JSON a `v1.0.0`, conservando commit, tags, image IDs y gzip; se volvió a validar su semántica. GitHub confirmó inmutabilidad, tag→SHA y seis digest/tamaños iguales a los bytes locales. El consumidor real aprobó preflight y todos los archivos con CAS simulado e idempotencia, sin OCI. `candidate` sigue rechazado como release instalable. Véase [contrato de release](../release-contract.md).

## Arquitectura y límites

Sentrux **no aprobado** contra el baseline vacío: calidad 7780→6596, complejidad 0→103 y coupling 0→0.07; cero ciclos y cero archivos dominantes. Se conserva el baseline. Referencia separada de la selección congelada: calidad 6589, 89 funciones complejas, coupling 0.0374, cero ciclos y cero archivos dominantes. La extracción conserva complejidad original y añade validadores; esa explicación no convierte el gate en aprobado.

Los seis skips locales son un servicio GIS que exige opt-in, cuatro comprobaciones Spark/JDK/Delta y Nginx local. Nginx se comprobó aparte realmente en Linux. No se invocaron modelos, actores pagados ni aceptación AIDP real.

Dos suites y archivos del instalador combinado permanecen como evidencia porque auto-review rechazó eliminarlos por posible debilitamiento de validación. No se reintentó ese borrado. No están importados por la aplicación ni incluidos en la imagen. `apps/backend/tests/validation-scope.json` conserva la clasificación y sus sustitutos; no se declara aprobada toda la suite histórica.

Avisos npm heredados: un crítico DOMPurify y siete altos permanecen. La revisión del consumidor Cesium no encontró los modos necesarios para el crítico y añadió una regresión específica; los altos corresponden a QA/build o rutas dev no observadas. No equivale a un audit limpio ni a garantía sobre usos futuros. El pin upstream no se modificó para ocultarlos.

Arko guía responsabilidades; no se declara `arko check` aprobado para este layout conservado. Los tests de composición/cierre verifican independencia. No se inicializó Graphify. Windows requiere temporales pytest nuevos y escalación por ACLs, sin borrar corridas previas.

## Entrega y aceptación pendiente

El coordinador posee Browser, Docker compartido, colas y mutaciones OCI. La prueba autorizada seguirá Governance→Market→GodEye sobre **un solo AIDP**. GodEye debe usar `aidp_mode=existing`, el OCID y workspace exactos producidos por la primera instalación y el administrador del dominio seleccionado. Esos identificadores todavía no se conocen en este candidato; no se inventan ni se sustituyen por nombres.

1. Desplegar y aceptar el handoff privado genérico CTN junto con este consumidor. La consulta local real a `trusted_deployment_project` aún rechaza el proyecto como no deployable; registrar/habilitar el catálogo corresponde al coordinador. Usar fuente `ref=v1.0.0`, SHA exacto y `release_tag=v1.0.0`. Mantener privado, sin tokens GitHub en hooks/VM.
2. Aceptación OCI por el coordinador: permisos efectivos, VM, recuperación, bindings existentes, negativas de acceso, task outputs/publicación y conversación de la revisión instalada. No se amplía a evaluación de respuestas ni actores pagados.
3. Revisar Sentrux no aprobado y avisos heredados antes de promover producción.

Revisión independiente acotada del handoff: se corrigió la falta de vínculo con `source.ref` y se añadió regresión; hallazgo cerrado. Tests focalizados: 68 aprobados, incluidos 33 del consumidor local. La división entre implementación y revisión permitió detectar esa omisión; no se midieron ahorro ni tokens. Baseline anterior a esta adaptación: Sentrux ya degradado, calidad 6589 y 102 funciones complejas; baseline original conservado.

La comprobación final de bytes publicados se ejecutó con escalación por las ACLs Windows, igual que pytest; no se borraron corridas anteriores. El intento sin escalación no pudo acceder a su temporal y no constituye un check aprobado. Secret scan final: 512 archivos no ignorados, sin patrones de secretos; no lee `.oci` ni imprime valores. Diff check aprobado. Los cambios posteriores al commit de código son solo documentación y recibo de release.

Codex: GPT-6.1 Sol Medium -- integración de contratos, permisos y recuperación. [Referencia](https://learn.chatgpt.com/docs/model-selection)

## Corrección de primer arranque v1.0.1

Se retiraron campos manuales de origen, TLS, imagen/AD y bundle. La IP de la VM determina origen/callback; preflight deriva imagen/AD compatibles y bundle desde el código fijado. TLS se genera dentro de la VM, con huella pública por OCI y confianza exclusiva en la hoja para health. Un único servicio recibe/activa; Resume y la entrega completada son idempotentes. Se comprueban los IDs activos antes de declarar instalación. La revisión del host incluye bundle y plantilla; un host incompatible requiere recuperación explícita.

Pruebas focalizadas: 63 aprobadas, incluida ejecución del receptor generado, TLS SSL real y comando OpenSSL público. Revisión independiente: hallazgos de pin TLS, selección/paginación, salida PEM, permisos y Resume corregidos; sin hallazgos abiertos. El primer postflight dio 1671 aprobadas/6 omitidas y tres mocks Terraform; el postflight final repitió los mismos resultados con la revisión completa del host. Sentrux sigue degradado frente al baseline vacío (calidad 6606, complejidad 104, coupling 0.07, cero ciclos/archivos dominantes). El SHA/CI y la release de esta corrección se registrarán en el cierre.

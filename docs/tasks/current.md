# Candidato de migración God’s Eye View

Estado: candidato local validado y publicado en el repositorio privado. El consumidor del handoff privado ya está implementado; la integración CTN y aceptación nativa siguen pendientes. No se hicieron mutaciones OCI. La publicación privada autorizada para la prueba se registrará al verificar sus seis assets.

## Repositorio y alcance

- Destino: `D:/dev/codex-aidp-ai-gods-eye-view`.
- Remoto privado: `https://github.com/jgangini/aidp-ai-gods-eye-view`; permiso ADMIN verificado. No se cambió su visibilidad.
- El código anterior `dd71b530cfbb48e721a14437f13faaa7169a4471` pasó CI. Esta revisión añade el consumidor del handoff local; su SHA/CI y release se registrarán en el cierre documental posterior.
- Fuente congelada: `3c82617fd298933995e954955841007253cc0985`. Extracción de 417 archivos versionados, con procedencia y hashes; sin `.oci`, estado ni caches.
- Requisitos: [diagnóstico](../migration-assessment.md) y contrato de separación del coordinador. Única interfaz integrada al visor; instalación por Deploy Studio.

## Implementación

API propia `app.main:create_app`, OIDC, membresía/revocación y RBAC por OCID y roles AIDP directos, grupos y roles heredados. Controles social/sensor/proveedores integrados al visor upstream fijado. Los programas AIDP conservan Gold, Object Storage, CAS, checkpoints y cuatro computes separados. El usuario lector necesita membresía actual; administrar requiere además el administrador seleccionado y su rol efectivo vigente.

Terraform implementa AIDP new/existing con recursos externos fuera del state administrado. Hooks verifican identidad y administrador, registran recursos exactos y rechazan adopción por nombre o cambio de plataforma/workspace/catalog al reanudar. El bundle VM es determinista y se verifica por SHA. La entrega OCI/TLS está cifrada y ligada al operador, fingerprint y deployment. Seleccionar administrador no suplanta al firmante. Compose publica solo el gateway TLS y usa imágenes locales por ID inmutable. Updates rechazan rotación implícita de credenciales OCI o TLS.

El consumidor local del handoff privado valida contexto, repositorio/ref/SHA, seis assets, manifiestos y bytes antes de mutar recursos; usa snapshots verificados y CAS. El descargador HTTP aislado conserva sus tests, pero no es llamado por los hooks. El consumidor VM verifica bytes, ID y plataforma. El manifiesto activo no pide un token GitHub ni supone `GH_TOKEN`/`GITHUB_TOKEN` en hooks. Preflight y post-apply rechazan el prerequisito ausente antes de mutar recursos. El [contrato mínimo de handoff](../private-artifact-handoff.md) distingue implementación actual y adaptación pendiente.

## Validación del código exacto

- Preflight: baseline Sentrux guardado antes de extraer código, con 5 archivos y calidad 7780. Sin reglas propias ni grafo Graphify.
- Postflight `scripts/arch-postflight.ps1` sobre la integración handoff: **1625 passed, 6 skipped**, tres programas y tres manifests de fuentes AIDP verificados, Terraform validate y dos escenarios mock new/existing aprobados. El comando completo termina con error por el gate Sentrux descrito abajo.
- [CI 42145571020](https://github.com/jgangini/aidp-ai-gods-eye-view/actions/runs/42145571020): seis jobs aprobados sobre ese SHA: Python, Terraform, frontend y builds/paquetes de las imágenes API, visor y gateway. Los dos CI anteriores de integración también aprobaron. Se corrigieron las dos causas del primer CI fallido; no se rebajaron assertions.
- Frontend: 89 tests y build React aprobados. Visor: 119 tests nativos y build de 753 módulos aprobados con Node 24.14.0. Puente: 143 tests aprobados. Los lotes focalizados se solapan con el postflight y no se suman como cobertura distinta.
- Nginx real Linux: autorización, outage y passthrough aprobados en contenedor existente, sin red y con mounts explícitos readonly. Rollback del script probado con Docker simulado: restaura configuración e imágenes del mismo recibo y conserva puntero/checksums.
- API Docker construida desde base local existente; smoke sin red/puertos aprobado: health, rechazo anónimo, ausencia de endpoint deploy y exclusión de código histórico/evaluación. Pydantic de producción alineado con la versión probada.
- Parser Pydantic y extractor **reales** de Deploy Studio, sobre el ZIP completo de Git HEAD `dd71b530`: **46.588.360 bytes** de archivo; **87 archivos / 1.129.764 bytes** seleccionados. Límites reales de Settings: 100 MiB de archivo GitHub, 250 archivos y 10 MiB extraídos. No se ampliaron.
- En la imagen existente de CTN, sin red y montando solo esos 87 archivos: imports de ambos hooks aprobados; `build_vm_bundle.build()` produce **16.995 bytes**. Sin dependencias accidentales del árbol completo.
- CI produce tres archivos de imagen y tres manifiestos `release=candidate`, más un bundle VM separado. `candidate` se rechaza deliberadamente como release estable instalable. Véase [contrato de release](../release-contract.md).

## Arquitectura y límites

Sentrux **no aprobado** contra el baseline vacío: calidad 7780→6596, complejidad 0→103 y coupling 0→0.07; cero ciclos y cero archivos dominantes. Se conserva el baseline. Referencia separada de la selección congelada: calidad 6589, 89 funciones complejas, coupling 0.0374, cero ciclos y cero archivos dominantes. La extracción conserva complejidad original y añade validadores; esa explicación no convierte el gate en aprobado.

Los seis skips locales son un servicio GIS que exige opt-in, cuatro comprobaciones Spark/JDK/Delta y Nginx local. Nginx se comprobó aparte realmente en Linux. No se invocaron modelos, actores pagados ni aceptación AIDP real.

Dos suites y archivos del instalador combinado permanecen como evidencia porque auto-review rechazó eliminarlos por posible debilitamiento de validación. No se reintentó ese borrado. No están importados por la aplicación ni incluidos en la imagen. `apps/backend/tests/validation-scope.json` conserva la clasificación y sus sustitutos; no se declara aprobada toda la suite histórica.

Avisos npm heredados: un crítico DOMPurify y siete altos permanecen. La revisión del consumidor Cesium no encontró los modos necesarios para el crítico y añadió una regresión específica; los altos corresponden a QA/build o rutas dev no observadas. No equivale a un audit limpio ni a garantía sobre usos futuros. El pin upstream no se modificó para ocultarlos.

Arko guía responsabilidades; no se declara `arko check` aprobado para este layout conservado. Los tests de composición/cierre verifican independencia. No se inicializó Graphify. Windows requiere temporales pytest nuevos y escalación por ACLs, sin borrar corridas previas.

## Entrega y aceptación pendiente

El coordinador es único dueño de Browser, Docker compartido, colas y mutaciones OCI. La prueba autorizada seguirá Governance→Market→GodEye sobre **un solo AIDP**. GodEye debe usar `aidp_mode=existing`, el OCID y workspace exactos producidos por la primera instalación, y el administrador del dominio seleccionado. Esos identificadores todavía no se conocen en este candidato; no se inventan ni se sustituyen por nombres.

1. Desplegar y aceptar el handoff privado genérico CTN junto con el consumidor implementado, sin tokens GitHub en hooks/VM. Mantener privado mientras no exista otra decisión explícita.
2. Preparar/publicar la primera release estable privada inmutable del consumidor validado y verificar sus seis assets. La autorización de prueba real permite esa preparación necesaria; no elimina el bloqueo técnico.
3. Aceptación OCI por el coordinador: permisos efectivos, VM, recuperación, bindings existentes, negativas de acceso, task outputs/publicación y conversación de la revisión instalada. No se amplía a evaluación de respuestas ni actores pagados.
4. Revisar el gate Sentrux no aprobado y los avisos heredados antes de promover producción.

Codex: GPT-6.1 Sol Medium -- integración de contratos, permisos y recuperación. [Referencia](https://learn.chatgpt.com/docs/model-selection)

Revisión independiente acotada del handoff: se corrigió la ausencia de vínculo con `source.ref` y se añadió regresión; hallazgo cerrado. Tests focalizados: 68 aprobados, incluidos 33 del consumidor local. Baseline previo de esta adaptación: Sentrux ya degradado, calidad 6589 y 102 funciones complejas; baseline original conservado.

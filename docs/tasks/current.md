# Candidato de migración God’s Eye View

Estado: candidato ejecutable localmente, con integración final/CI en curso. La instalación privada queda bloqueada por el handoff de artefactos del control plane y la decisión de visibilidad pendiente. No se hicieron mutaciones OCI ni se publicó una release.

## Repositorio y alcance

- Destino: `D:/dev/codex-aidp-ai-gods-eye-view`.
- Remoto: `https://github.com/jgangini/aidp-ai-gods-eye-view`, verificado privado y con permiso ADMIN. Se conserva esa visibilidad.
- Primer commit publicado en main: `b82f492a0fa568eda1ad45392ba1e13715f1e37c`. Los cambios de integración posteriores están pendientes de commit/push final al actualizar esta sección.
- Fuente congelada: `3c82617fd298933995e954955841007253cc0985`. Se extrajeron 417 archivos versionados con procedencia y hashes; no se copiaron `.oci`, estado ni caches.
- Requisitos: diagnóstico `../migration-assessment.md`, subordinado al plan común del coordinador. Única interfaz integrada al visor; instalación por Deploy Studio.

## Implementación y evidencia

API propia con fábrica `app.main:create_app`, OIDC, membresía/revocación y RBAC por OCID y roles AIDP directos, grupos y roles heredados. No hay portal, login local ni rutas de instalación HTTP. Controles social/sensor/proveedores integrados al visor upstream fijado. Los programas AIDP conservan Gold, Object Storage, CAS, checkpoints y cuatro computes separados.

Terraform implementa selección AIDP new/existing con recursos externos fuera del state administrado. Hooks verifican identidad y administrador, registran recursos exactos y rechazan adopción por nombre. El bundle VM es determinista y se verifica por SHA. La entrega OCI/TLS está cifrada y ligada a operador/fingerprint/deployment; seleccionar administrador no suplanta al firmante. Compose solo publica el gateway TLS y usa imágenes locales por ID inmutable.

El descargador de assets privados, aislado en `scripts/deployment/image_assets.py`, está probado con HTTP simulado y CAS. El cargador VM verifica bytes, image ID y plataforma antes de activar. No se supone `GH_TOKEN`/`GITHUB_TOKEN` en el hook ni se declara un token de descarga en el manifiesto activo. El coordinador debe cerrar el handoff genérico desde control plane, o adaptar HTTPS anónimo si el usuario decide hacer públicos los repositorios. La decisión no está aprobada por silencio; preflight y post-apply rechazan ese prerequisito faltante antes de mutar recursos.

CI genera artifacts privados de candidato; no los trata como release estable instalable. El empaquetador produce gzip determinista, manifiesto, SHA y plataforma para las tres imágenes. Los dos updaters anteriores de visor/portal se sustituyeron con mapping en `../release-contract.md`.

## Checks realmente ejecutados

- Preflight: baseline Sentrux guardado antes de extraer código (5 archivos, calidad 7780). No reglas propias ni grafo Graphify.
- Postflight integrado anterior a los últimos cambios de entrega privada: 1517 passed, 6 skipped; tres programas y tres manifests de fuentes AIDP verificados; Terraform validate y dos escenarios mock new/existing passed. Debe repetirse por los cambios de integración posteriores.
- Frontend: 89 tests passed sin cambiar assertions; build React passed. Visor: 119 tests nativos y build de 753 módulos passed con Node 24.14.0.
- Puente actualizado: 143 tests passed. Nginx real Linux: prueba de outage/autorización/passthrough passed, en contenedor sin red con mounts explícitos readonly.
- Entrega privada: 35 tests del descargador/inspector, 26 del empaquetador y pruebas del consumidor VM/cifrado/guards passed en lotes focalizados. Último lote previo a añadir health/handoff: 69 passed. Estos lotes no se suman para fingir cobertura distinta.
- Rollback real del script con Docker simulado: restaura runtime.env e imágenes del mismo recibo, conserva puntero y checksums; passed.
- API Docker construida desde base local existente; smoke aislado sin red/puertos passed: health, rechazo anónimo, ausencia de endpoint deploy y exclusión de código combinado/evaluación. Se alineó Pydantic con la versión de pruebas y se reconstruyó la imagen.
- Parser Pydantic y extractor de archivo reales Deploy Studio: passed para el candidato y paths/entrypoints/include_paths. Revalidación final del manifiesto modificado pendiente.
- Secret scan: 504 archivos no ignorados, sin patrones de claves/tokens; no lee `.oci` ni imprime valores. Repetir antes de push final.
- CI inicial `42141235844` sobre b82f492: Terraform e imágenes API/gateway passed; frontend falló por omitir `--output` y Python por referencia al Nginx antiguo. Ambos corregidos con evidencia; siguiente corrida pendiente de push.

## Arquitectura y límites

El gate Sentrux **no está aprobado**: contra el repo vacío, calidad 7780→6587, complejidad 0→98 y coupling 0→0.07. Se conservó el baseline. Comparación adicional con la selección congelada del mismo producto: calidad 6589, 89 funciones complejas, coupling 0.0374. Ambos tienen cero ciclos y cero archivos dominantes. La extracción conserva la complejidad original y añade integración/validadores; estos números no equivalen a un gate aprobado ni justifican sobrescribir el baseline.

Seis skips locales: servicio GIS externo requiere opt-in; cinco comprobaciones necesitan Spark/JDK/Delta o Nginx. La comprobación Nginx se ejecutó aparte realmente en Linux. No se invocaron modelos, actores de pago ni aceptación AIDP real.

Dos archivos/suites del instalador combinado permanecen como evidencia porque auto-review rechazó eliminarlos por posible debilitamiento de validación. No se reintentó ese borrado; no están importados por la aplicación ni incluidos en la imagen. Sus sustitutos y selección del gate están en `apps/backend/tests/validation-scope.json`; no se declara aprobada la suite histórica completa.

Avisos npm heredados: DOMPurify crítico requiere modos ausentes del consumidor Cesium localizado y tiene regresión específica; siete avisos altos se relacionan con QA/build o rutas dev no observadas en preview Linux. No se confirmó alcance productivo en esa revisión; los paquetes siguen presentes y deben reevaluarse si cambia su uso. No se actualizó el pin para ocultar los avisos.

Arko guía responsabilidades, pero no se declara `arko check` aprobado: su perfil actual no valida directamente el layout de módulos conservado. La independencia se verifica con tests reales de composición y cierre. En Windows se usan temporales nuevos `.local/pytest-*`, sin borrar corridas previas; ACLs requieren escalación para pytest.

## Gates restantes

1. Finalizar checks de los últimos cambios, commit/push y CI verde del candidato exacto.
2. Decisión explícita de visibilidad y contrato genérico de handoff privado a cargo del coordinador. No hay token supuesto ni native readiness simulada.
3. Release estable inmutable con seis assets verificados, todavía no publicada.
4. Aceptación OCI serializada por coordinador: IAM/roles, bootstrap de VM, new/existing, recuperación tras interrupciones y permisos negativos; task outputs/publicación y conversación de la revisión instalada.
5. Sentrux permanece informado como no aprobado frente al baseline vacío; revisión de las diferencias nuevas y deuda de complejidad antes de promover producción.

Codex: GPT-6.1 Sol Medium -- integración de contratos, permisos y recuperación. [Referencia](https://learn.chatgpt.com/docs/model-selection)

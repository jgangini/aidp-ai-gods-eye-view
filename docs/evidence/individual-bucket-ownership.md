# Cinco modos de bucket: candidato v2.1.0

Fuente `ca0c4a5dbfd8614c5aacfc03aaf3b62419038a33`, [PR #1](https://github.com/jgangini/aidp-ai-gods-eye-view/pull/1), [CI 42272619772](https://github.com/jgangini/aidp-ai-gods-eye-view/actions/runs/42272619772). El contrato vigente está en [Instalación e identidad](../contracts.md), con recuperación en [Operación](../operations.md).

## Comportamiento y acceso

Artifacts tiene modo new/existing propio, textbox nuevo y selector `oci_active_buckets`. Las cuatro filas de Medallion Architecture siguen el mismo patrón, con modos independientes y defaults `oci_landing`, `oci_bronze`, `oci_silver`, `oci_gold`; Artifacts usa `oci_artifacts`. La normalización exige las cinco elecciones y nombres distintos, y genera nombres canónicos y `bucket_modes`. El parámetro global y su fallback se retiraron del contrato actual.

Terraform conserva las direcciones `oci_objectstorage_bucket.product[layer]` y `prevent_destroy`. Solo los modos new entran en el `for_each`; los existentes no se adoptan. Una retirada de un bucket ya gestionado debe bloquearse, no transferir ownership. Los reutilizados deben ser accesibles en el endpoint regional elegido y pertenecer al compartimento del despliegue; se bloquean redirects y reutilización con un compartimento aún no creado. No se amplió IAM al tenancy. Post-apply compara nombres/modos con los outputs y revalida ubicación antes del journal. Artifacts debe conservar su identidad al reanudar; el selector no implementa una migración del almacenamiento ni de `user_data`.

El visor sigue usando OIDC de OCI Identity Domains, con el administrador seleccionado y permisos AIDP efectivos. La administración de VM usa OCI Compute Instance Run Command. No se añadieron cuentas locales, campos Username/Password, credenciales SSH ni regla 22; la entrada pública continúa en 443.

## Validación

- Foco final: **301 pruebas aprobadas**, incluidas las 32 combinaciones de modos, ambas formas del contexto de compartimento, colisiones, rechazo legacy, nombres inválidos, scope/errores SDK y bloqueos antes del journal. El test del cliente usa el Session real del SDK para comprobar que una redirección regional falla antes de seguirla.
- La primera corrida Terraform colocaba los escenarios mixtos después de un apply de cinco buckets. Terraform rechazó retirar Artifacts mediante `prevent_destroy`. Se conservó la protección y se ordenaron los planes independientes antes del apply.
- Postflight final: `scripts/arch-postflight.ps1`, **1948 passed, 6 skipped**, tres programas y tres manifiestos AIDP verificados, formato/validate y **ocho mocks Terraform aprobados**, incluidas mezclas e inputs incompletos. El comando global termina con error por Sentrux.
- CI: seis jobs aprobados; Python 1948 passed / seis skips, controles 89 tests/build, visor 119 tests/build, rollback simulado y tres imágenes empaquetadas. Los skips locales son GIS opt-in, cuatro escenarios Spark/JDK/Delta y Nginx; en CI Nginx pasa y el sexto skip es el consumidor CTN externo, comprobado localmente. No sumar corridas como cobertura distinta.
- El coordinador reportó parser backend estricto aprobado y SSR real con defaults all-new y all-existing: schema 2, ocho grupos, 23 campos. No se añadieron overrides o fallback CTN. Browser/OCI reales corresponden al coordinador; este chat no los ejecutó.
- ZIP del commit: **46.660.380 bytes**, selección CTN de **88 archivos / 1.176.951 bytes**, dentro de 100 MiB / 250 archivos / 10 MiB. El output no sensible `bucket_modes` está declarado para sobrevivir al filtro de state del runner.
- Bundle CI de 22.709 bytes: SHA-256 `7fab22b0c20c405f79718b58b77071f64c99dd4d3c0c61ea0c7bc57bf44a4a7b`. Revisión Linux del host V2 `77909c23cfa39ac899a9c04e817cd2290fee4ccdbc16f6bea2acf708c37737d5`, sin cambios.
- Sentrux: preflight 6610, postflight 6620, coupling 0,07, 104 funciones complejas, cero ciclos/god files. Sigue DEGRADED frente al baseline inicial 7780 conservado. No hay reglas propias; no se declara aprobado el gate global.
- Graphify existente actualizado y wiki exportada: **3993 nodos, 11388 aristas, 171 comunidades y 181 artículos**, sin endpoints colgantes; fuente `ca0c4a5d`, cero tokens LLM. La extracción paralela falló con WinError 5 y la herramienta completó secuencialmente. Falta `tree_sitter_hcl`, por lo que HCL no aporta símbolos; su comportamiento se comprobó con Terraform. No se inicializó otro grafo, generó visualización ni incluyó archivos locales Graphify en el commit del producto.

## Assets y gate de publicación

El [borrador v2.1.0](https://github.com/jgangini/aidp-ai-gods-eye-view/releases/tag/untagged-cc7c0f93c35593fa008c), ID `436861738`, tiene seis assets ligados al SHA de fuente anterior. IDs, tamaños y SHA-256 remotos coinciden con el paquete de CI/promoción. El [recibo del candidato](../releases/v2.1.0-candidate.json) conserva los valores exactos. El handoff pasó con Artifacts existente y Medallion nuevo, desde inputs sin tag/prefijo operativos; también pasó la comparación contra outputs. CAS simulado hizo tres cargas iniciales y ninguna al repetir, sin OCI.

Se inspeccionaron estáticamente tres imágenes, 34 capas únicas, 80.909 archivos y 1.565.695.178 bytes, incluidas capas históricas, sin ejecutarlas. Los 68 archivos con coincidencias conocidas conservaron su hash. Seis candidatos `.pyc` nuevos conservan sus payloads compilados; solo varían los encabezados de 16 bytes. No se imprimieron valores candidatos. Las seis releases anteriores mantuvieron IDs, assets, tamaños, hashes e inmutabilidad.

**La candidata sigue como draft, sin publicación ni inmutabilidad todavía.** Desde este chat no se intentó publicarla. Después de asumir esa operación, el coordinador reportó un intento exacto rechazado realmente por auto_review: la autorización registrada cubre v2.0.1, y se exige aprobación específica para v2.1.0 y marcarla como latest. El comando no se ejecutó. El coordinador ya presentó la pregunta concreta al usuario y retomará tras su respuesta; no se reintentó ni se cambió el paquete.

La publicación no acredita aceptación OCI ni conversación del agente. Persisten el gate Sentrux no aprobado y los [avisos de dependencias heredados](native-dependency-review.md). No se realizaron migraciones, adopciones, retiradas de state ni operaciones sobre recursos compartidos.

# Releases e imágenes

Las [releases públicas](https://github.com/jgangini/aidp-ai-gods-eye-view/releases) distribuyen tres imágenes `linux/amd64`: API, visor y gateway. Una release instalable debe ser estable `vMAJOR.MINOR.PATCH`, inmutable, sin draft/prerelease y apuntar al mismo commit que la fuente seleccionada en Deploy Studio. No instalar desde una rama móvil ni mezclar `release_tag` y ref distintos.

## Contenido

Cada componente aporta un gzip Docker y un manifiesto JSON: exactamente los seis nombres del [contrato de entrega](private-artifact-handoff.md). Los JSON schema 1/updater_protocol 1 fijan repositorio, tag, commit, archivo SHA-256, plataforma, tag canónico e ID inmutable de imagen. El consumidor revalida metadata, archivos y contenido antes de activar.

El bundle de bootstrap de VM es otro artifact, calculado desde el código y publicado en Object Storage por el hook. No se adjunta como séptimo asset.

## Preparación de una release

El [workflow CI](../.github/workflows/ci.yml) ejecuta comprobaciones y construye/empaqueta las tres imágenes. `scripts/release/package_candidate.py` recibe una imagen ya construida; no construye, descarga ni publica imágenes. Verifica ID/plataforma, fija tag canónico por commit y produce gzip/manifiesto con hashes.

Los artifacts CI con `release=candidate` no son instalables. La preparación estable debe conservar los gzip y sus IDs/tags/commit, fijar la release estable en los JSON y volver a validar su semántica y hashes. Antes de publicar el borrador, comprobar los seis assets remotos y sus tamaños/digests. Publicar con inmutabilidad habilitada y verificar tag→commit. Una corrección requiere otra versión; no sobrescribir assets ni tags inmutables.

El repositorio público no permite publicar perfiles OCI, archivos de entorno, claves, estado Terraform o datos operativos. Revisar historial y contenido de imágenes, incluidas capas anteriores y metadata de build, antes de exponer material nuevo.

## Instalación y actualización

Deploy Studio entrega los seis assets verificados al hook; la VM usa imágenes locales por ID, sin pulls de registro ni tokens GitHub. La revisión del host combina bundle y plantilla de arranque. Un Update de imágenes requiere la misma revisión; migrar un bootstrap distinto exige recuperación autorizada del host. [Operación](operations.md) describe Resume, recibos y rollback.

Una release publicada o un CI aprobado no acreditan instalación OCI, permisos efectivos, confianza del certificado en Browser ni conversación del agente. El post-apply mantiene esas comprobaciones diferenciadas.

## Evidencia y pruebas

- Recibos publicados: [v1.0.3](releases/v1.0.3.json), [v1.0.2](releases/v1.0.2.json), [v1.0.1](releases/v1.0.1.json), [v1.0.0](releases/v1.0.0.json). Sus manifiestos schema 1 requieren un motor compatible con ese contrato.
- Candidato [v2.0.0](releases/v2.0.0-candidate.json): formulario completo schema 2, borrador pendiente de publicación; [evidencia de formulario y validación](evidence/deploy-studio-form-schema2.md).
- La [preparación histórica de v1.0.3](evidence/deploy-studio-runner-contract.md) conserva su [recibo original de borrador](releases/v1.0.3-candidate.json).
- [Verificación de imágenes y CAS](../tests/test_image_assets.py), [carga VM](../tests/test_image_assets_vm.py) y [empaquetado](../tests/test_release_candidate.py).
- [Rollback reproducible](../docker/tests/bootstrap-rollback.sh) y [alcance de validación](../apps/backend/tests/validation-scope.json).
- El historial de extracción y los informes de ejecución se mantienen en `docs/migration-assessment.md`, `docs/extraction-provenance.json` y `docs/tasks/`; no son instrucciones de instalación.

Las releases existentes permanecen inmutables. Sus notas conservan el contexto de publicación original; la visibilidad actual del repositorio no altera sus bytes ni hashes.

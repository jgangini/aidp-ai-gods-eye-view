# Desarrollo y validación

Python 3.12, Node 24.14.0 para el visor, Terraform con OCI 8.28.0 fijado. Instalar dependencias en un entorno propio; conservar `.oci`, `.local`, node_modules, `.upstream` y state fuera de Git/imágenes.

```powershell
./scripts/arch-preflight.ps1
./.venv/Scripts/python.exe scripts/check_product.py
npm test --prefix apps/frontend
npm run build --prefix apps/frontend
node --test modules/ai-gods-eye-view/tests/*.test.mjs
node modules/ai-gods-eye-view/native/runtime.mjs --build
./scripts/arch-postflight.ps1
```

El preparador `modules/ai-gods-eye-view/prepare_upstream.py` materializa la fuente fijada; sus dependencias se instalan con `npm ci --ignore-scripts` dentro de `.upstream`. El build standalone retenido no sustituye al build nativo. El workflow CI construye las tres imágenes, sin publicar una release final.

`scripts/check_product.py` es la ruta integrada de Python/renderizado/Terraform. Exige que toda suite transferida esté clasificada en `apps/backend/tests/validation-scope.json`. Las dos suites del instalador combinado antiguo permanecen como evidencia fuera del gate de producto, con sustitutos indicados; no se presentan como checks aprobados. Los temporales pytest son directorios nuevos bajo `.local`, sin borrar ejecuciones anteriores. En Windows puede requerirse escalación de sandbox por ACL; no cambiar assertions para eludirla.

Sentrux usa la ruta CLI y su baseline original. No hay reglas propias ni grafo Graphify. La importación de código a un repo inicialmente vacío incrementa complejidad respecto al baseline inicial: se conserva ese resultado y se compara además con la extracción congelada del mismo producto, sin sobrescribir el baseline. El estado exacto queda en `tasks/current.md`; un gate degradado no equivale a aprobado.

Arko guía responsabilidades, contratos y consumidores. Su perfil CLI actual presupone un layout distinto de los módulos conservados; no se declara `arko check` aprobado. El manifiesto AIDP y tests de independencia comprueban explícitamente el cierre actual.

Antes de commit/push: `scripts/scan_secrets.py`, `git diff --check`, revisión de paths seleccionados y estado del remoto privado. El escáner imprime solo paths/reglas, nunca valores. Es detección por patrones, no garantía de ausencia de todo secreto posible. Las comprobaciones reales y sus límites están en el registro de tarea.

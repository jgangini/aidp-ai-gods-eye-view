# God’s Eye View para Oracle AIDP

Visor territorial con evidencia social, sensores, publicaciones Gold y agente LangGraph. La configuración de streaming y proveedores está integrada al visor. Instalación, reanudación y actualización pertenecen a Deploy Studio.

Este repositorio es un **candidato de extracción**, procedente del commit `3c82617fd298933995e954955841007253cc0985` de Starter Kits. No acredita aún una instalación nativa nueva ni una transición de instalaciones existentes. No contiene el portal de Starter Kits.

- [Contratos e instalación](docs/contracts.md)
- [Desarrollo y validación](docs/development.md)
- [Operación y límites del candidato](docs/operations.md)
- [Diagnóstico y procedencia](docs/migration-assessment.md)
- [Progreso y evidencia](docs/tasks/current.md)

API FastAPI propia con OIDC y RBAC, controles React integrados y visor upstream fijado por commit/hash. El gateway TLS es la única entrada pública; API, bridge y Node permanecen en la red interna. Lectores no administran. Las consultas usan Gold de AIDP; controles y diarios usan Object Storage, sin dependencia Autonomous para lectores/escritores.

El upstream nativo se conserva en `modules/ai-gods-eye-view/upstream.json`. Su build requiere Node 24.14.0 y el preparador verifica archive y parches. Nunca se descarga una rama móvil al arrancar. Los avisos de dependencias y sus límites de aplicabilidad están en la guía del visor; los checks locales no sustituyen aceptación nativa o revisión de cambios upstream.

El primer arranque corregido deriva imagen/AD compatibles y el bundle desde el código fijado. La URL usa la IP asignada y la VM genera su clave TLS local; Deploy Studio devuelve certificado público y huella para establecer confianza antes de OIDC. No requiere que el usuario aporte un dominio, certificado, clave TLS ni hash/objeto de bundle. Véanse las limitaciones de confianza, renovación y actualización del host en [operación](docs/operations.md).

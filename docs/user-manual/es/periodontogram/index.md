---
module: periodontogram
last_verified_commit: 84c03fa4
---

# Periodontograma

El módulo de **periodontograma** añade el diagnóstico y seguimiento
periodontal SEPA a la ficha clínica del paciente. Vive como una
sub-pestaña dentro del modo **Diagnóstico**, junto al odontograma.
Cada exploración se guarda como un snapshot fechado e inmutable, lo
que permite comparar la evolución del paciente entre sesiones.

Es un módulo **opcional**: no se instala por defecto. Para activarlo,
ve a *Admin → Módulos → Periodontograma → Instalar*.

## Pantallas

- [Vista del periodontograma](../patients/screens/detail.md#periodontogram) -
  exploración SEPA, captura por celda, banner de índices, slider de
  histórico. Es una sub-vista de la ficha del paciente y se documenta
  como sección de esa página.

## ¿Qué captura cada exploración?

Por diente (dentición permanente 11–48):

- Implante (sí / no — se prerellena leyendo el odontograma).
- Movilidad Miller (0–3).
- Pronóstico individual (Bueno / Medio / Dudoso / Sin esperanza).
- Furca vestibular y lingual / palatina (0 / I / II / III) — solo molares.
- Anchura encía queratinizada (mm).

Por sitio (6 sitios por diente: MV, V, DV, ML, L, DL):

- Profundidad de sondaje (0–15 mm).
- Margen gingival (-5 a +10 mm, negativo = hiperplasia).
- Sangrado al sondaje (sí / no).
- Placa visible (sí / no).
- Supuración (sí / no).

## Índices computados al cerrar

| Índice | Definición |
|--------|------------|
| BoP % | % de sitios medidos con sangrado al sondaje. |
| PI % | % de sitios medidos con placa. |
| CAL medio | Media del nivel de inserción clínica (sondaje + margen). |
| Bolsas ≥5 mm | Nº de dientes con al menos un sitio ≥ 5 mm. |

Los índices se calculan automáticamente y se congelan en el snapshot
al cerrar. Se muestran en el banner superior del periodontograma.

## Flujo típico

1. **Abrir sesión** desde la sub-pestaña *Periodontograma*. El sistema
   crea un borrador (estado `draft`) y prerellena dientes ausentes e
   implantes leyendo el odontograma del paciente.
2. **Capturar datos** clicando en cualquier celda. Los cambios se
   autoguardan a los 600 ms; el banner inferior indica el estado
   (Guardando… / Cambios pendientes / Guardado).
3. **Cerrar sesión** desde la botonera inferior. Antes de cerrar el
   sistema vuelca los cambios pendientes; al confirmar, los índices
   se computan y el snapshot queda inmutable.
4. **Navegar el histórico** con el slider superior: cada nodo es un
   snapshot cerrado. El banner ámbar avisa cuando estás viendo una
   exploración pasada.

## Limitaciones conocidas

- **Solo dentición permanente.** Los dientes deciduos (51–85) no
  están en el alcance del periodontograma SEPA.
- **Las sesiones cerradas no se editan.** Para corregir, abre una
  sesión nueva.
- **Pantalla pequeña.** La vista SEPA completa requiere al menos
  1024 px de ancho. En tabletas verticales y móviles aparece scroll
  horizontal — un layout por cuadrante con swipe está planeado para
  una fase posterior.

## Permisos

| Rol | Acceso |
|-----|--------|
| admin / dentista | Total. |
| higienista | Crear, editar y cerrar sesiones. |
| asistente | Solo lectura. |
| recepcionista | No ve la sub-pestaña. |

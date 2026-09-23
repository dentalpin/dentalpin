# Embedded OHIF viewer wiring

`StudyViewer.vue` loads `/ohif/viewer?study=<StudyInstanceUID>`.

- **With a vendored build:** run `build-from-source.sh` (pinned `v3.12.14`).
  It drops the dist next to `ohif-config.js`, which points the viewer at our
  DICOMweb-minimal proxy (`/api/v1/imaging_viewer/dicomweb/...`, same JWT
  session). The `dist/` output is untracked.
- **Without it:** the component falls back to the original-file download —
  that is the current default and is fully supported.

License: OHIF/Viewers is MIT (© 2018 Open Health Imaging Foundation); the
notice is preserved in the module `NOTICE.md`. The dist is never committed.

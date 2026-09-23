/**
 * OHIF v3 data-source config template for the DentalPin embedded viewer.
 *
 * Pinned build: OHIF/Viewers v3.12.14 (MIT — see module NOTICE.md).
 * Copy this file next to the vendored viewer dist as `ohif-config.js` and
 * serve them together from this directory. The viewer iframe
 * (StudyViewer.vue) passes `?study=<StudyInstanceUID>`; the config below
 * resolves studies/frames against our clinic-scoped DICOMweb-minimal proxy
 * (same JWT session — no separate credentials).
 *
 * Proxy surface (all under the studies.read gate):
 *   QIDO  GET /api/v1/imaging_viewer/dicomweb/studies?patient_id=<uuid>
 *   WADO  GET /api/v1/imaging_viewer/dicomweb/studies/{uid}/series/{s}/instances/{i}/frames/{n}
 */
window.config = {
  routerBasename: '/ohif',
  showStudyList: false,
  dataSources: [
    {
      namespace: '@ohif/extension-default.dataSourcesModule.dicomweb',
      sourceName: 'dentalpin',
      configuration: {
        friendlyName: 'DentalPin archive',
        name: 'dentalpin',
        qidoRoot: '/api/v1/imaging_viewer/dicomweb',
        wadoRoot: '/api/v1/imaging_viewer/dicomweb',
        qidoSupportsIncludeField: false,
        supportsReject: false,
        imageRendering: 'wadors',
        thumbnailRendering: 'wadors',
        enableStudyLazyLoad: true,
        supportsFuzzyMatching: false,
      },
    },
  ],
  defaultDataSourceName: 'dentalpin',
}

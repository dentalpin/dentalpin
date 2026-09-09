Official Agenzia delle Entrate schema for FatturaPA, downloaded from
<https://www.fatturapa.gov.it/export/documenti/fatturapa/v1.2.2/Schema_del_file_xml_FatturaPA_v1.2.2.xsd>
(the v1.2.3 file is not published at a stable URL; 1.2.3 only adds
enumeration values on top of 1.2.2). The only edit is the `schemaLocation`
of the xmldsig import, pointed at the vendored W3C copy so the test suite
validates offline.

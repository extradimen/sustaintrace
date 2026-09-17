# SustainTrace Source Distribution Policy

SustainTrace publishes its code, schemas, derived facts, evidence coordinates, and failure-repair
records under the project license. The distribution does not include original corporate PDF
reports. Each source document is assigned to one of the following classes in the machine-readable
manifest:

1. `redistributable`: the source has an explicit redistribution license and may be included in an
   example package. At present, only project-generated smoke-test PDFs use this class.
2. `official_auto_download`: a stable issuer-hosted direct URL is available. A user may explicitly
   download the document after installation, after which SustainTrace verifies its frozen SHA256.
   Downloading a report does not alter its copyright status.
3. `official_manual_download`: only an official landing page is available. The user must obtain the
   document in accordance with the publisher's terms.
4. `metadata_only`: no stable reproducible public URL is available. The release stores only the
   title, issuer, document identifier, and frozen hash.

The current trusted release seed references 34 reports. Eight are registered for official direct
download and 26 are released as metadata only. None of the 34 original PDFs is bundled.

The authoritative machine-readable record is
`data/manifests/release_source_distribution_v0.1.lock.json`.

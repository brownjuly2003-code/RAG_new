# Capability: Corpus provenance

<!-- Durable spec: it outlives the run. One capability per file; MyFlow injects the requirements a task
     references into the WorkOrder and the review pack. Format is OpenSpec-compatible. -->

The 201-document air-cargo corpus is the source of every retrieval number this
repository publishes, and it is not in git: `data/*` is ignored, the copy on
`D:\Archive` was lost, and until 2026-09-06 the only known copy lived on one
Mac. A number measured over a corpus nobody can re-identify is not evidence.

## Requirement: a published number names a corpus that can be verified from git

The system SHALL keep, in git, a manifest that identifies every file of a
measured corpus by name and SHA-256 together with an aggregate digest over the
whole set, and SHALL provide a command that verifies a local corpus directory
against that manifest without needing the network.

### Scenario: the corpus on this machine is the corpus a number was measured over

- **GIVEN** a checked-in corpus manifest and a local corpus directory
- **WHEN** the verify command runs against them
- **THEN** it exits 0 and prints the aggregate digest and the file count

### Scenario: a corpus that drifted is rejected, and the drift is named

- **GIVEN** a checked-in manifest and a local corpus where one file's bytes
  changed, one file is missing and one extra file was added
- **WHEN** the verify command runs
- **THEN** it exits non-zero and names each of the three files under the
  category it failed in — changed, missing, extra — rather than only reporting
  that the aggregate digest differs

### Scenario: the manifest is reproducible

- **GIVEN** an unchanged corpus directory
- **WHEN** the manifest is built twice
- **THEN** both runs produce byte-identical manifest content, so a rebuild in a
  diff means the corpus changed and nothing else

## Requirement: the aggregate digest is stable under filesystem accidents

The aggregate corpus digest SHALL be computed over the file names and their
content digests in a fixed sorted order, SHALL hash file content as raw
bytes, SHALL ignore hidden files (names starting with `.`), and SHALL
normalise file names to Unicode NFC, so that directory listing order,
line-ending translation on checkout, a macOS `.DS_Store`, NFD versus NFC
spellings of the same name, or the machine the corpus is read on cannot
change the published number.

The stored root SHALL be a repo-relative POSIX path when the corpus sits
inside the project, and the stable placeholder `<external>` otherwise —
never an absolute path.

### Scenario: two machines agree on the digest

- **GIVEN** the same corpus present on two machines
- **WHEN** the manifest is built on each
- **THEN** the aggregate digest is the same on both

### Scenario: a hidden sidecar is not a corpus file

- **GIVEN** a corpus directory that also contains a file whose name starts with `.`
- **WHEN** the manifest is built or verified
- **THEN** that file is not listed, does not change `corpus_sha256`, and is
  not reported as extra

### Scenario: NFD and NFC spellings of a name are the same corpus file

- **GIVEN** a corpus file whose name is stored as Unicode NFD on one machine
  and NFC on another
- **WHEN** the manifest is built on each
- **THEN** both produce one entry under the NFC name and the same
  `corpus_sha256`

### Scenario: a corpus outside the repository does not embed a machine path

- **GIVEN** the same corpus bytes at two different locations outside the
  project root
- **WHEN** the manifest is built for each
- **THEN** the stored root is not an absolute path, and the two manifests
  are byte-identical

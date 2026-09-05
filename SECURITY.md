# Security policy

## Supported versions

Security fixes are provided for the latest released minor line, currently
**0.5.x**. Upgrade to its newest patch release and read the
[upgrade guide](docs/upgrading-to-0.5.md); upgrading alone cannot reconstruct data
that an earlier version stored incorrectly. Older release lines do not receive
backported fixes under this policy.

## Reporting a vulnerability

Email the maintainer at [script3r@gmail.com](mailto:script3r@gmail.com). GitHub
private vulnerability reporting is not currently enabled for this repository;
do not open a public issue containing a suspected vulnerability or sensitive
reproduction data.

Include the affected version, database backend, impact, and a minimal
reproduction using synthetic data and disposable test keys. Do not send
production keys, credentials, customer data, or production plaintext/ciphertext.
The maintainer aims to acknowledge reports within seven days; disclosure timing
will be coordinated after investigation.

## Scope and known limitations

Unexpected plaintext storage, authentication failures that are silently ignored,
incorrect key loading or invalidation, and behavior contrary to the package's
documented guarantees are relevant reports. This includes package defects that
expose keys; key exposure is not categorically excluded from review.

Deterministic equality leakage, visible ciphertext length/nullness, and the
absence of row-specific AAD by default are documented properties. The package
does not protect data after decryption inside a compromised application or
replace application authentication, authorization, logging controls, or KMS
access policies.

Deterministic key rotation does not automatically preserve cross-generation
lookups or plaintext uniqueness. Backend-dependent serialization can also affect
equality. These are known limitations, not features provided by the cache API.
See [operations and limitations](docs/operations.md) and the
[0.5.0 upgrade guide](docs/upgrading-to-0.5.md) for migration and recovery details.

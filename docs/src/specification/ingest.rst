.. _specification-ingest-label:

Ingest
======

The direct ingest protocol is a lightweight command/response alternative to :doc:`insert`,
for high-throughput producers. It does not use :doc:`../misc_pkgs/pub_sub`: the repo listens
for Interests directly, and each command is a single Interest/Data exchange.

1. The repo registers an Interest filter on ``/<repo_name>/ingest``.

2. The producer sends a signed Interest under ``/<repo_name>/ingest`` carrying an ``ObjParam``
   as its application parameters. The InterestSignatureInfo must contain ``SignatureTime``
   and ``SignatureNonce``. Since the ``params-sha256=<digest>`` name component covers both the
   parameters and the signature, every command Interest has a distinct name, even when it
   carries the same parameters as an earlier one. ``ObjParam`` has the following fields:

   * ``name``: either a Data packet name, or a name prefix of segmented Data packets.
   * ``forwarding_hint`` (Optional): forwarding hint used to fetch ``name``, same
     semantics as in :doc:`insert`.
   * ``start_block_id`` (Optional): inclusive start segment number.
   * ``end_block_id`` (Optional): inclusive end segment number.
   * ``register_prefix`` (Optional): tell the repo to start serving reads under this prefix
     once the data is stored.

   See :doc:`encoding` for the ``ObjParam`` ABNF and TLV-TYPE assignments.

3. The repo fetches and stores Data as in step 3 of :doc:`insert`.

4. Once all requested packets are fetched and stored, the repo acks by replying to the
   original ingest Interest with an empty Data packet.

5. If the command fails, the repo replies to the original ingest Interest with an empty
   Data packet whose ``ContentType`` is ``NACK``. The producer may retry by sending the
   command again as a new signed Interest, which has a new name. There is no status/check
   protocol for ingest (contrast with :doc:`check`, available for :doc:`insert` and
   :doc:`delete`).

The repo must reply before the ingest Interest expires, so fetching is bounded by its
``InterestLifetime``; if fetching does not finish in time, the repo replies with a NACK.
Ingest commands are idempotent, so resending a command is safe.

Ingest commands are authorized with a trust schema. The repo is configured with a trust
anchor certificate and a `Light VerSec (LVS)
<https://python-ndn.readthedocs.io/en/latest/src/lvs/lvs.html>`_ trust schema in the
``ingest_security`` section of its configuration file. For each ingest Interest, the repo:

* replies with a NACK if the Interest is unsigned, or if its InterestSignatureInfo lacks
  ``SignatureTime`` or ``SignatureNonce``;
* checks the full Interest name, including the ``params-sha256`` component, and the
  KeyLocator against the trust schema;
* fetches the certificate named by the KeyLocator, and each issuer certificate in turn, until
  it reaches the trust anchor, checking every certificate against the trust schema;
* verifies each signature along the chain.

Interests that fail validation are dropped without a reply, before the repo fetches or stores
any Data. The KeyLocator must therefore name a certificate (not a key) that the repo can
fetch. If ``ingest_security`` is not configured, the repo does not register
``/<repo_name>/ingest`` and the protocol is disabled. Other repo protocols are not affected
by this configuration.

The trust anchor is the CA certificate at the root of the producer certificate chains; it is
not a pin for one producer. Multiple producers can use the same repo when their certificates
chain to this anchor and the LVS schema authorizes their certificate names. Producers issued
by different, unrelated roots require separate repo configurations or additional validator
support, which this implementation does not provide.

Configure the trust anchor and schema paths in the repo YAML file. The anchor may be an NDN
certificate in wire format or base64-encoded wire format. ``~`` and environment variables in
both paths are expanded::

    ingest_security:
      trust_anchor: '~/.ndn/trust/trust-anchor.ndncert'
      trust_schema: '/etc/ndn-python-repo/ingest.lvs'

The repo reads and compiles the text schema at startup, so the configured schema file must be
readable and valid LVS. A sample schema is provided at ``ndn_python_repo/ingest.lvs.sample``.

For example, this schema authorizes two producer namespaces issued by the same root to send
ingest commands to ``/repo``::

    #KEY: "KEY"/_/_/_
    #root: "example"/#KEY
    #producer_a: "example"/"producer-a"/#KEY <= #root
    #producer_b: "example"/"producer-b"/#KEY <= #root
    #ingest: "repo"/"ingest"/_ <= #producer_a | #producer_b

Replace the example names and component patterns with the names in the actual NDN certificates.
``#root`` must match the configured trust-anchor certificate, each producer rule must match
the corresponding producer certificate name, and each producer rule must be listed as an
allowed signer of ``#ingest``. The final ``_`` in ``#ingest`` matches the
``params-sha256`` component. A producer certificate may be fetched only if its certificate
name is routable from the repo.

.. note::
   ``register_prefix`` registrations are kept only in memory, not persisted like
   :doc:`insert`, and are lost on repo restart. Also, unlike :doc:`insert`, the repo does not
   check whether ``name`` overlaps with its own ``/<repo_name>`` namespace. The trust schema
   authorizes the command Interest signer only; it does not restrict which ``name`` an
   authorized producer may ingest. ``SignatureTime`` and ``SignatureNonce`` are currently
   required to be present, but the repo does not enforce a time window or detect nonce
   replays. Certificate validity periods are also not checked by python-ndn's chain validator.

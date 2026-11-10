.. _specification-ingest-label:

Ingest
======

The direct ingest protocol is a lightweight command/response alternative to :doc:`insert`,
for high-throughput producers. It does not use :doc:`../misc_pkgs/pub_sub`: the repo listens
for Interests directly, and each command is a single Interest/Data exchange.

1. The repo registers an Interest filter on ``/<repo_name>/ingest``.

2. The producer sends an unsigned Interest under ``/<repo_name>/ingest``. Its application
   parameters are a signed Data packet, the *command Data*, encoded with its outer TLV and
   named ``/<repo_name>/ingest/<timestamp>/<nonce>``, where ``<timestamp>`` is a Timestamp
   name component and ``<nonce>`` is a random component. The command Data carries an
   ``ObjParam`` as its Content. Since the ``params-sha256=<digest>`` name component covers the
   command Data, every command Interest has a distinct name, even when it carries the same
   ``ObjParam`` as an earlier one. ``ObjParam`` has the following fields:

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
   command again with a new command Data, so the Interest has a new name. There is no status/check
   protocol for ingest (contrast with :doc:`check`, available for :doc:`insert` and
   :doc:`delete`).

Both the ack and the NACK are signed with the key of the repo's default identity, and the
KeyLocator names its certificate. The producer should validate the reply with its own trust
schema before treating the command as acknowledged or rejected; an unsigned or invalid reply
must be ignored.

The repo must reply before the ingest Interest expires, so fetching is bounded by its
``InterestLifetime``; if fetching does not finish in time, the repo replies with a NACK.
Ingest commands are idempotent, so resending a command is safe.

Ingest commands are authorized with a trust schema. The repo is configured with a trust
anchor certificate and a `Light VerSec (LVS)
<https://python-ndn.readthedocs.io/en/latest/src/lvs/lvs.html>`_ trust schema in the
``ingest_security`` section of its configuration file. For each ingest Interest, the repo:

* drops the Interest if it is signed, if its application parameters are not a Data packet,
  or if that Data is not named ``/<repo_name>/ingest/<timestamp>/<nonce>``. These commands
  violate the protocol, so the repo does not reply to them;
* checks the command Data name and its KeyLocator against the trust schema;
* fetches the certificate named by the KeyLocator, and each issuer certificate in turn, until
  it reaches the trust anchor, checking every certificate against the trust schema;
* verifies each signature along the chain.

Commands that fail validation are dropped without a reply, before the repo fetches or stores
any Data. A command whose Content is not a valid ``ObjParam`` passes validation but is
answered with a NACK. The KeyLocator must therefore name a certificate (not a key) that the repo can
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
      trust_schema: '/etc/ndn-python-repo/ingest.lvsb'

``trust_schema`` is normally the LVS binary format, compiled from the trust schema at a
central location and distributed to each repo. As an alternative, it may be LVS text, which
the repo compiles at startup. The repo tells the two formats apart by the first TLV-TYPE of
the binary format. To compile a text schema into the binary format with python-ndn::

    python3 -c 'import sys; from ndn.app_support.light_versec import compile_lvs; sys.stdout.buffer.write(compile_lvs(sys.stdin.read()).encode())' < ingest.lvs > ingest.lvsb

In either format, the configured schema file must be readable and valid LVS. A sample schema is provided at ``ndn_python_repo/ingest.lvs.sample``.

For example, this schema authorizes two producer namespaces issued by the same root to send
ingest commands to ``/repo``::

    #KEY: "KEY"/_/_/_
    #root: "example"/#KEY
    #producer_a: "example"/"producer-a"/#KEY <= #root
    #producer_b: "example"/"producer-b"/#KEY <= #root
    #ingest: "repo"/"ingest"/_/_ <= #producer_a | #producer_b

Replace the example names and component patterns with the names in the actual NDN certificates.
``#root`` must match the configured trust-anchor certificate, each producer rule must match
the corresponding producer certificate name, and each producer rule must be listed as an
allowed signer of ``#ingest``. The final two ``_`` in ``#ingest`` match the
``<timestamp>`` and ``<nonce>`` components of the command Data name. A producer certificate may be fetched only if its certificate
name is routable from the repo.

.. note::
   ``register_prefix`` registrations are kept only in memory, not persisted like
   :doc:`insert`, and are lost on repo restart. Also, unlike :doc:`insert`, the repo does not
   check whether ``name`` overlaps with its own ``/<repo_name>`` namespace. The trust schema
   authorizes the command Interest signer only; it does not restrict which ``name`` an
   authorized producer may ingest. The ``<timestamp>`` and ``<nonce>`` components are
   currently required to be present, but the repo does not enforce a time window or detect
   replays. Certificate validity periods are also not checked by python-ndn's chain validator.

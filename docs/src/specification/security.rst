Overall
=======

The repo is considered as part of the NDN network infrastructure.
Therefore, when deployed for production,
the security requirements are supposed to be specified by the authority,
such as the network operator or the project manager.

For development deployment or internal use, the settings described in this section are recommended.

Required Settings
-----------------

- All Interests with application parameters are required to be signed. Otherwise the Repo must drop the Interest.
  Currently including the check Interest ``/<repo_name>/<command> check`` and the publication notification Interest
  ``"/<topic>/notify"``.
- Check Interests are required to have at least one of ``SignatureTime``, ``SignatureNonce``, or ``SignatureSeqNum``.
  Otherwise, Check Interests' result is undefined behavior.
  This is to make sure these check Interests are different to avoid cache invalidation.

.. warning::
  Unfortunately current implementation does not follow these requirements by default.
  This may cause some potential vulnerabilities. Will be fixed in future versions.


Recommended Settings
--------------------

- Packet signatures should be signed by asymmetric algorithms. Use ECDSA or Ed25519 when in doubt.
- Signed Interests should use ``SignatureNonce``.

  - Since there is no replay attack, the Repo does not have to remember the list of ``SignatureNonce``.

- If the Repo is provided as a network service, the certificate obtained from the network provider should be used.
  In this case, the prefix registration command and repo's publication data are signed using the same key.

  - For example, if one employs a Repo as a public service of NDN testbed,
    then both the client and the Repo server should use their testbed certificates.
  - The Repo should use the same verification method as its local NFD node to verify the register.
  - The client should use the same verification method as how it verifies the prefix registration command.

- If the Repo is provided as an application service, it should either obtain an identity from the application namespace,
  or runs on its own trust domain and holds the trust anchor.
  In this case, the prefix registration command and repo's publication data are signed using different keys.

  - In this case, the Repo is supposed obtain the trust schema when it is bootstrapped into the application's namespace.
    If it is unable to obtain the trust schema, it should maintain a user list to verify the clients.
    The client should do similar things.

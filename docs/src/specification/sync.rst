Joining SVS Sync (Draft)
========================

- Joining SVS Sync group is an optional feature. It should only be enabled when it is deployed as a network service.

  - If the Repo is deployed as an application service,
    the application deployer should run another process on the same node as an SVS peer and use the Repo only for Data.

- The Repo should not join an application's SVS sync group as a producer.
  (unless the sync group is specifically designed for Repos to backup data)

- The Repo should learn how to verify the target SVS group's Sync Interest.

- The Repo should store its received latest SVS notification Interest as is,
  and responds with this Interest when it hears some out-of-dated SVS vector.

- If there are multiple latest SVS state vectors, e.g. ``[A:1, B:2]`` and ``[A:2, B:1]``,
  the Repo will not be able to merge them into ``[A:2, B:2]``.
  Instead, it should respond with both stored Interests eventually.
  Maybe all at once, maybe one at one time. Not decided yet.

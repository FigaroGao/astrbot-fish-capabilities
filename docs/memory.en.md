# Long-term memory boundaries

The original device uses customized [LivingMemory](https://github.com/lxfight-s-Astrbot-Plugins/astrbot_plugin_livingmemory) for shared-group and individual-member memory. It is not an independent vector store bundled with the capability plugin.

Reference upstream baseline: b8aaaec2c1232ec2c86fce22cec066a0069018e0, AGPL-3.0. Changes span storage, retrieval, reflection, commands, and tool entry points. Copying only group_layers.py cannot reproduce complete two-layer memory. These changes are not yet a portable patch and are excluded; installation does not reproduce that system.

Tablets can use cloud embeddings: remote vector computation with local index storage/search. The reference uses Alibaba Cloud embeddings with 1024 dimensions. Verify your available model rather than copying its ID. Back up and rebuild compatible indexes before changing dimensions.

Check conversation, group, and member isolation. Validate real metadata after vector retrieval, rejecting private, other-group, and unknown-source results. A shared-group-memory prompt label cannot replace data isolation. Do not share private history to give the group bot access to it.

Retrieval filtering does not replace isolation checks across prompts, tools, histories, and caches. This distribution does not guarantee absolute absence of leaks and contains no user memories or databases.

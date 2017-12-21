# Overview

ArangoDB is a native multi-model, open-source database with flexible
data models for documents, graphs, and key-values. This charm installs and
configures [ArangoDB](https://arangodb.com/).

# Usage

Deploy the ArangoDB charm with the following:

```bash
juju deploy cs:~tengu-team/arangodb-1
```
The ArangoDB UI is then available at `http://x.x.x.x:8592`. If the root password is not provided in the `config.yaml`, then the root password will be auto-generated and will be shown in the status of the charm.


# Clustering
The ArangoDB charm supports clustering but will need at least 3 units to work in cluster mode. This charm uses the default configuration for cluster where every unit will act as DB server and Coordinator.

#### 2 units
If a model contains 2 units then there are two possible situations on how the charms will behave.

1) If a unit was added and the model upgraded from 1 to 2 units, then the first unit that was created will be available in standalone mode while the second unit will get in a blocked state.

2) If a unit was removed while ArangoDB was running in cluster mode, Then both of the units will get in a blocked state.

# Limitations
- When a unit is removed in cluster mode, The UI will still show this node in his cluster but with an exclamation mark next to it. The User can then choose to remove it from the list.


# Contact Information

## Authors

 - Dixan Peña Peña <dixan.pena@tengu.io>
 - Sébastien Pattyn <sebastien.pattyn@tengu.io>

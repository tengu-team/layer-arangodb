# Overview

ArangoDB is a native multi-model, open-source database with flexible
data models for documents, graphs, and key-values. This charm installs and 
configures [ArangoDB](https://arangodb.com/).

# Usage

Deploy the ArangoDB charm with the following:

```bash
juju deploy cs:~tengu-team/arangodb-0
```
The ArangoDB UI is then available at `http://x.x.x.x:8592`. If the root password is not provided in the `config.yaml`, then the root password will be auto-generated and will be shown in the status of the charm.

# Limitations
- At this moment ArangoDB can only run in stand-alone mode. Clustering ArangoDB with this charm is still in progress.
- The charm currently provides a http interface but will provide a custom interface which will also provide the root password.

# Contact Information


## Authors

 - Dixan Peña Peña <dixan.pena@tengu.io>

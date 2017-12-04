# Overview

ArangoDB is a native multi-model, open-source database with flexible
data models for documents, graphs, and key-values. This charm installs and 
configures [ArangoDB](https://arangodb.com/).

# Usage

Deploy the ArangoDB charm with the following:

```bash
juju deploy cs:~tengu-team/arangodb-0
```
The Arangodb UI is then available at `http://x.x.x.x:8592`

# Limitations
- At this moment ArangoDB can only run in stand-alone mode. Clustering ArangoDB with this charm is still in progress.

# Contact Information


## Authors

 - Dixan Peña Peña <dixan.pena@tengu.io>

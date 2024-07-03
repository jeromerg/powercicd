# Power CI/CD

!!! WORK IN PROGRESS !!!

Utility to automate the CI/CD process for Power Platform projects.

## Requirements

- Python 3.11 or later
- git

## Installation

```powershell
# install python if you don't have it
winget install python.python.3.11

# ALTERNATIVE 1: WITHOUT VIRTUAL ENVIRONMENT
pip install powercicd

# ALTERNATIVE 2: WITH VIRTUAL ENVIRONMENT
py -3.11 -m venv venv
.\venv\Scripts\Activate.ps1
pip install powercicd 
```

## Example

- prepare a powerbi workspace `my-workspace-dev` in your own tenant, e.g. `mytenant.onmicrosoft.com`
- copy the example project `.\doc\examples\my_project\` to your local machine
- init git in the project folder
  - `git init`
- edit the `power-project-dev.yaml`
  - change the `tenant` to the name of your tenant, e.g. `mytenant.onmicrosoft.com`
- cd to the project folder

### Open the powerbi report *my_report*

```powershell
function pow { python -m powercicd.pow $args }
pow export_to_pbix my_report
```
## Development

### Requirements

- Python 3.11 or later
- git
- poetry

```powershell
```

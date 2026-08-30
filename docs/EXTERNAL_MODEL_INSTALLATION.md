# External model installation and execution placement

Verified on 2026-08-25 for the current Windows laptop (Core Ultra 5 125H,
16 GB RAM, integrated Intel Arc graphics). A smoke test establishes technical
execution only, never scientific or personal predictive validity.

| Component | Local status | Execution placement | Boundary |
|---|---|---|---|
| OpenSim / Moco | Smoke verified | Local small runs; remote optimization sweeps | Not subject calibrated |
| FEBio | Smoke verified | Local technical/small meshes; remote anatomical meshes and sweeps | Technical Model4 coupling only |
| Pulse | Smoke verified | Local | Not personalized or predictively validated |
| CircAdapt | Smoke verified | Local | Reference model only |
| HumMod | Smoke verified | Local reference | Legacy/manual reference, not a core coupling |
| PK-Sim | Smoke verified | Local | Technical PBPK runtime |
| MoBi / OSPSuite-R | Model consumption verified | Local | Mapping efficacy unvalidated |
| Human-GEM / COBRApy | Load/solve verified | Local | Constraint solution is not physiology truth |
| MitoCore | Load/solve verified | Local reference | Reference model only |
| Mitochondrial QSP | Finite integration verified | Local small runs | Paper reproduction/personal validity absent |
| MyoSuite 2.12.2 | Environment reset/step verified | Local inference; remote RL training | Random step only |
| PhysiCell 1.14.2 | Official Windows template verified | Local small models; remote custom builds/large populations | No repair model qualified |
| libCellML 0.7.0 | CellML 2.0 round-trip verified | Local | No specific physiological model selected |
| SimVascular svVascularize 0.0.50 | Python/VTK import verified | Local geometry/low fidelity; remote 3D CFD/FSI | Full desktop/solver not local |
| SPARC client / Zinc | Client import verified | Local public-data interface; cloud for large datasets | Credentials required for restricted services |
| OpenCap Core | Official source installed | Supported cloud processing | Account and compatible iOS capture devices required |
| Harvey / Harvetta | Not downloaded | VMH authenticated model generation, then local COBRA solve | VMH account required |
| VMH | Public service verified | Remote data/API service | Not a local simulator |
| Sim4Life | Not installed | Licensed workstation/server or Sim4Life Web | User license/account required; 4 GB installer alone is not executable authority |

## Runtime placement rule

The laptop owns Codex orchestration, typed input construction, immutable
experiment records, small reproducibility checks, and result analysis. Remote runners own high-resolution
FEBio, SimVascular 3D/FSI, large PhysiCell populations, MyoSuite learning, Sim4Life,
and large parameter sweeps. Remote results must return versioned artifact hashes,
simulated time, terminal status, units, provenance, and limitations before they can
enter a scientific draft.

## Outstanding user-controlled prerequisites

1. VMH account access for generated Harvey and Harvetta assets.
2. OpenCap account plus compatible iOS capture devices for a real motion session.
3. Sim4Life license/account if that optional high-fidelity branch is selected.
4. A remote compute target before high-resolution or large-sweep execution begins.

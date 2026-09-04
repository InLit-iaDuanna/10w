# Forge Shell third-party notices

This module pins the following packages in `frontend/pnpm-lock.yaml`:

| Package | Version | License | Use |
|---|---:|---|---|
| dockview-react | 8.2.0 | MIT | sole production docking engine |
| react | 19.2.8 | MIT | local compile/test peer |
| react-dom | 19.2.8 | MIT | local compile/test peer |
| typescript | 6.0.3 | Apache-2.0 | strict type checking |
| @types/node | 22.20.1 | MIT | test-runner types |
| @types/react | 19.2.18 | MIT | React types |
| @types/react-dom | 19.2.7 | MIT | React DOM types |

The application composition root remains responsible for collecting these notices into the product-level notice bundle.

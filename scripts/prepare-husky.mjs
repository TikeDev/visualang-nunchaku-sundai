import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';

const isProductionInstall =
  process.env.CI === 'true' ||
  process.env.RENDER === 'true' ||
  process.env.NODE_ENV === 'production';
const huskyBin = process.platform === 'win32' ? 'node_modules/.bin/husky.cmd' : 'node_modules/.bin/husky';

if (isProductionInstall || !existsSync('.git') || !existsSync(huskyBin)) {
  process.exit(0);
}

const result = spawnSync(huskyBin, { stdio: 'inherit' });
process.exit(result.status ?? 0);

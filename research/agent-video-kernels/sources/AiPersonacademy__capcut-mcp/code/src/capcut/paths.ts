import path from 'path';
import fs from 'fs/promises';
import { existsSync } from 'fs';
import { RootMetaInfo, RootDraftStoreItem } from './types.js';

export class CapCutPathResolver {
  private static cachedDraftsPath: string | null = null;

  /**
   * Returns the absolute path to CapCut's drafts folder.
   */
  public static getDraftsDirectory(): string {
    if (this.cachedDraftsPath && existsSync(this.cachedDraftsPath)) {
      return this.cachedDraftsPath;
    }

    // 1. Check explicit environment override
    if (process.env.CAPCUT_DRAFTS_PATH && existsSync(process.env.CAPCUT_DRAFTS_PATH)) {
      this.cachedDraftsPath = path.resolve(process.env.CAPCUT_DRAFTS_PATH);
      return this.cachedDraftsPath;
    }

    const localAppData = process.env.LOCALAPPDATA || '';

    // 2. Standard CapCut Desktop path
    const capcutStandard = path.join(localAppData, 'CapCut', 'User Data', 'Projects', 'com.lveditor.draft');
    if (existsSync(capcutStandard)) {
      this.cachedDraftsPath = capcutStandard;
      return capcutStandard;
    }

    // 3. JianYing (Chinese CapCut variant) path
    const jianyingStandard = path.join(localAppData, 'JianyingPro', 'User Data', 'Projects', 'com.lveditor.draft');
    if (existsSync(jianyingStandard)) {
      this.cachedDraftsPath = jianyingStandard;
      return jianyingStandard;
    }

    // 4. Default to standard path even if not yet created
    this.cachedDraftsPath = capcutStandard;
    return capcutStandard;
  }

  /**
   * Allows setting a custom drafts path (useful for testing or non-standard installs)
   */
  public static setDraftsDirectory(customPath: string): void {
    this.cachedDraftsPath = path.resolve(customPath);
  }

  /**
   * Returns the path to root_meta_info.json
   */
  public static getRootMetaPath(): string {
    return path.join(this.getDraftsDirectory(), 'root_meta_info.json');
  }

  /**
   * Reads root_meta_info.json, or returns a fresh structure if it does not exist.
   */
  public static async readRootMeta(): Promise<RootMetaInfo> {
    const rootPath = this.getRootMetaPath();
    if (!existsSync(rootPath)) {
      return {
        all_draft_store: [],
        draft_ids: 0,
        root_path: this.getDraftsDirectory().replace(/\\/g, '/')
      };
    }

    try {
      const content = await fs.readFile(rootPath, 'utf-8');
      return JSON.parse(content) as RootMetaInfo;
    } catch (err) {
      throw new Error(`Failed to read CapCut root_meta_info.json at ${rootPath}: ${err instanceof Error ? err.message : String(err)}`);
    }
  }

  /**
   * Writes updated root_meta_info.json atomically.
   */
  public static async writeRootMeta(meta: RootMetaInfo): Promise<void> {
    const rootPath = this.getRootMetaPath();
    const dir = path.dirname(rootPath);
    await fs.mkdir(dir, { recursive: true });

    const tempFile = `${rootPath}.tmp.${Date.now()}`;
    const jsonStr = JSON.stringify(meta);
    await fs.writeFile(tempFile, jsonStr, 'utf-8');
    await fs.rename(tempFile, rootPath);
  }

  /**
   * Resolves a draft directory by either its draft_id or draft_name.
   */
  public static async findProjectDir(nameOrId: string): Promise<{
    folderPath: string;
    item?: RootDraftStoreItem;
    isLocked: boolean;
  }> {
    const rootMeta = await this.readRootMeta();
    const draftsDir = this.getDraftsDirectory();

    // Look in root_meta_info store
    const item = rootMeta.all_draft_store.find(
      (d) => d.draft_id === nameOrId || d.draft_name === nameOrId
    );

    let folderPath: string;
    if (item && item.draft_fold_path && existsSync(item.draft_fold_path)) {
      folderPath = path.resolve(item.draft_fold_path);
    } else {
      // Try direct subfolder in drafts directory
      const direct = path.join(draftsDir, nameOrId);
      if (existsSync(direct)) {
        folderPath = direct;
      } else {
        throw new Error(`CapCut project '${nameOrId}' was not found in ${draftsDir}`);
      }
    }

    const lockPath = path.join(folderPath, '.locked');
    const isLocked = existsSync(lockPath);

    return { folderPath, item, isLocked };
  }

  /**
   * Locates CapCut executable on the system.
   */
  public static findCapCutExecutable(): string | null {
    const localAppData = process.env.LOCALAPPDATA || '';
    const capcutApps = path.join(localAppData, 'CapCut', 'Apps');

    if (existsSync(capcutApps)) {
      const directExe = path.join(capcutApps, 'CapCut.exe');
      if (existsSync(directExe)) {
        return directExe;
      }
    }

    return null;
  }
}

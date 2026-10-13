import { spawn } from 'child_process';
import { CapCutPathResolver } from './paths.js';

export class AppLauncher {
  /**
   * Launches CapCut Desktop application or opens the CapCut projects folder.
   */
  public static async launchCapCut(): Promise<{ success: boolean; message: string }> {
    const exePath = CapCutPathResolver.findCapCutExecutable();

    if (exePath) {
      const child = spawn(exePath, [], {
        detached: true,
        stdio: 'ignore'
      });
      child.unref();
      return {
        success: true,
        message: `Launched CapCut executable from: ${exePath}`
      };
    }

    // If direct exe not located, open via Windows explorer
    const draftsDir = CapCutPathResolver.getDraftsDirectory();
    const child = spawn('explorer.exe', [draftsDir], {
      detached: true,
      stdio: 'ignore'
    });
    child.unref();

    return {
      success: true,
      message: `Opened CapCut projects directory in Explorer: ${draftsDir}`
    };
  }

  /**
   * Opens a specific project folder in Windows Explorer.
   */
  public static async openProjectFolder(nameOrId: string): Promise<{ success: boolean; path: string }> {
    const { folderPath } = await CapCutPathResolver.findProjectDir(nameOrId);
    const child = spawn('explorer.exe', [folderPath], {
      detached: true,
      stdio: 'ignore'
    });
    child.unref();

    return {
      success: true,
      path: folderPath
    };
  }
}

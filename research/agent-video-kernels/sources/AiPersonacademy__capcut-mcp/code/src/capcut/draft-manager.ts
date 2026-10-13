import path from 'path';
import fs from 'fs/promises';
import { existsSync } from 'fs';
import { CapCutPathResolver } from './paths.js';
import { DraftBuilder } from './draft-builder.js';
import { MediaProbe } from './media.js';
import { SrtParser } from '../utils/srt-parser.js';
import {
  DraftContent,
  DraftMetaInfo,
  ProjectSummary,
  CreateProjectOptions,
  AddVideoClipOptions,
  AddAudioClipOptions,
  AddTextOptions,
  AddSubtitlesOptions,
  CanvasConfig,
  SubtitleItem,
  AddTransitionOptions,
  AddKeyframeOptions,
  AddStickerOptions,
  GeneratePreviewOptions,
  SplitClipOptions,
  SetClipSpeedOptions,
  AddAudioFadeOptions,
  AddViralCaptionOptions,
  CreateVideoBridgeOptions,
  AddSoundEffectOptions,
  AudioFadeMaterial,
  SpeedMaterial
} from './types.js';
import { PreviewRenderer } from './preview-renderer.js';

export class DraftManager {
  /**
   * Lists all projects registered in CapCut's root_meta_info.json,
   * along with their formatted duration and lock status.
   */
  public static async listProjects(): Promise<ProjectSummary[]> {
    const rootMeta = await CapCutPathResolver.readRootMeta();
    const results: ProjectSummary[] = [];

    for (const storeItem of rootMeta.all_draft_store) {
      const folderPath = storeItem.draft_fold_path ? path.resolve(storeItem.draft_fold_path) : '';
      const isLocked = folderPath && existsSync(path.join(folderPath, '.locked'));

      let tracksCount = 0;
      let videoTracksCount = 0;
      let audioTracksCount = 0;
      let textTracksCount = 0;
      let resolution = 'Unknown';
      let ratio = 'original';
      let fps = 30.0;

      // Try reading basic info from draft_content.json if accessible
      const draftContentPath = path.join(folderPath, 'draft_content.json');
      if (existsSync(draftContentPath)) {
        try {
          const contentRaw = await fs.readFile(draftContentPath, 'utf-8');
          const content = JSON.parse(contentRaw) as DraftContent;
          tracksCount = content.tracks?.length || 0;
          videoTracksCount = content.tracks?.filter(t => t.type === 'video').length || 0;
          audioTracksCount = content.tracks?.filter(t => t.type === 'audio').length || 0;
          textTracksCount = content.tracks?.filter(t => t.type === 'text').length || 0;
          if (content.canvas_config) {
            resolution = `${content.canvas_config.width}x${content.canvas_config.height}`;
            ratio = content.canvas_config.ratio;
          }
          if (content.fps) {
            fps = content.fps;
          }
        } catch {
          // Ignore parse errors on corrupted drafts
        }
      }

      const durationUs = storeItem.tm_duration || 0;
      const durationSec = Math.round((durationUs / 1_000_000) * 100) / 100;

      results.push({
        id: storeItem.draft_id,
        name: storeItem.draft_name,
        path: folderPath,
        durationSeconds: durationSec,
        durationFormatted: MediaProbe.formatDuration(durationUs),
        resolution,
        ratio,
        fps,
        tracksCount,
        videoTracksCount,
        audioTracksCount,
        textTracksCount,
        isLocked: !!isLocked,
        createTime: storeItem.tm_draft_create ? new Date(Math.floor(storeItem.tm_draft_create / 1000)).toISOString() : undefined,
        modifiedTime: storeItem.tm_draft_modified ? new Date(Math.floor(storeItem.tm_draft_modified / 1000)).toISOString() : undefined
      });
    }

    return results;
  }

  /**
   * Retrieves full details and timeline structure of a specific project.
   */
  public static async getProject(nameOrId: string): Promise<{
    summary: ProjectSummary;
    draftContent: DraftContent;
    draftMeta: DraftMetaInfo;
  }> {
    const { folderPath, isLocked } = await CapCutPathResolver.findProjectDir(nameOrId);
    const contentPath = path.join(folderPath, 'draft_content.json');
    const metaPath = path.join(folderPath, 'draft_meta_info.json');

    if (!existsSync(contentPath)) {
      throw new Error(`draft_content.json missing in project folder: ${folderPath}`);
    }

    const draftContent = JSON.parse(await fs.readFile(contentPath, 'utf-8')) as DraftContent;
    const draftMeta = existsSync(metaPath)
      ? JSON.parse(await fs.readFile(metaPath, 'utf-8')) as DraftMetaInfo
      : DraftBuilder.createEmptyDraftMeta(draftContent.id, draftContent.name || nameOrId, folderPath, CapCutPathResolver.getDraftsDirectory());

    const durationUs = draftContent.duration || 0;
    const summary: ProjectSummary = {
      id: draftContent.id,
      name: draftContent.name || path.basename(folderPath),
      path: folderPath,
      durationSeconds: Math.round((durationUs / 1_000_000) * 100) / 100,
      durationFormatted: MediaProbe.formatDuration(durationUs),
      resolution: draftContent.canvas_config ? `${draftContent.canvas_config.width}x${draftContent.canvas_config.height}` : '1080x1920',
      ratio: draftContent.canvas_config?.ratio || '9:16',
      fps: draftContent.fps || 30.0,
      tracksCount: draftContent.tracks?.length || 0,
      videoTracksCount: draftContent.tracks?.filter(t => t.type === 'video').length || 0,
      audioTracksCount: draftContent.tracks?.filter(t => t.type === 'audio').length || 0,
      textTracksCount: draftContent.tracks?.filter(t => t.type === 'text').length || 0,
      isLocked
    };

    return { summary, draftContent, draftMeta };
  }

  /**
   * Creates a new CapCut project draft from scratch and registers it in root_meta_info.json.
   */
  public static async createProject(options: CreateProjectOptions): Promise<ProjectSummary> {
    const draftsDir = CapCutPathResolver.getDraftsDirectory();
    await fs.mkdir(draftsDir, { recursive: true });

    // Sanitize folder name
    const folderName = options.name.replace(/[/\\?%*:|"<>]/g, '_');
    const projectFolder = path.join(draftsDir, folderName);

    if (existsSync(projectFolder)) {
      throw new Error(`A CapCut project folder already exists at '${projectFolder}'. Choose a different name.`);
    }

    await fs.mkdir(projectFolder, { recursive: true });

    // Determine canvas dimensions
    let width = options.width || 1080;
    let height = options.height || 1920;
    const ratio = options.ratio || '9:16';

    if (!options.width || !options.height) {
      switch (ratio) {
        case '16:9':
          width = 1920;
          height = 1080;
          break;
        case '1:1':
          width = 1080;
          height = 1080;
          break;
        case '4:3':
          width = 1440;
          height = 1080;
          break;
        case '9:16':
        default:
          width = 1080;
          height = 1920;
          break;
      }
    }

    const canvas: CanvasConfig = {
      ratio,
      width,
      height,
      background: null
    };

    const draftId = DraftBuilder.generateId();
    const fps = options.fps || 30.0;
    const draftContent = DraftBuilder.createEmptyDraftContent(draftId, options.name, canvas, fps);
    const draftMeta = DraftBuilder.createEmptyDraftMeta(draftId, options.name, projectFolder, draftsDir);

    // Write project files
    await fs.writeFile(
      path.join(projectFolder, 'draft_content.json'),
      JSON.stringify(draftContent),
      'utf-8'
    );
    await fs.writeFile(
      path.join(projectFolder, 'draft_meta_info.json'),
      JSON.stringify(draftMeta),
      'utf-8'
    );
    await fs.writeFile(
      path.join(projectFolder, 'draft_biz_config.json'),
      JSON.stringify({ draft_enterprise_info: { enterprise_material: [] } }),
      'utf-8'
    );

    // Register into root_meta_info.json
    const rootMeta = await CapCutPathResolver.readRootMeta();
    const nowUs = Date.now() * 1000;

    rootMeta.all_draft_store.unshift({
      draft_id: draftId,
      draft_name: options.name,
      draft_fold_path: projectFolder.replace(/\\/g, '/'),
      draft_json_file: path.join(projectFolder, 'draft_content.json').replace(/\\/g, '/'),
      draft_cover: path.join(projectFolder, 'draft_cover.jpg').replace(/\\/g, '/'),
      tm_duration: 0,
      tm_draft_create: nowUs,
      tm_draft_modified: nowUs,
      tm_draft_removed: 0,
      draft_root_path: draftsDir.replace(/\\/g, '/')
    });

    if (rootMeta.draft_ids !== undefined) {
      rootMeta.draft_ids += 1;
    }

    await CapCutPathResolver.writeRootMeta(rootMeta);

    return {
      id: draftId,
      name: options.name,
      path: projectFolder,
      durationSeconds: 0,
      durationFormatted: '0s',
      resolution: `${width}x${height}`,
      ratio,
      fps,
      tracksCount: 1,
      videoTracksCount: 1,
      audioTracksCount: 0,
      textTracksCount: 0,
      isLocked: false
    };
  }

  /**
   * Duplicates an existing CapCut project with regenerated IDs.
   */
  public static async duplicateProject(sourceNameOrId: string, newName: string): Promise<ProjectSummary> {
    const { folderPath, isLocked } = await CapCutPathResolver.findProjectDir(sourceNameOrId);
    if (isLocked) {
      throw new Error(`Cannot duplicate project '${sourceNameOrId}' while it is open in CapCut Desktop. Please exit the project first.`);
    }

    const { draftContent, draftMeta } = await this.getProject(sourceNameOrId);
    const newDraftId = DraftBuilder.generateId();

    const draftsDir = CapCutPathResolver.getDraftsDirectory();
    const sanitizedName = newName.replace(/[/\\?%*:|"<>]/g, '_');
    const newFolderPath = path.join(draftsDir, sanitizedName);

    if (existsSync(newFolderPath)) {
      throw new Error(`Project folder '${newFolderPath}' already exists.`);
    }

    await fs.mkdir(newFolderPath, { recursive: true });

    // Deep clone content and update IDs
    const clonedContent: DraftContent = JSON.parse(JSON.stringify(draftContent));
    clonedContent.id = newDraftId;
    clonedContent.name = newName;
    const nowUs = Date.now() * 1000;
    clonedContent.create_time = nowUs;
    clonedContent.update_time = nowUs;

    // Deep clone meta
    const clonedMeta: DraftMetaInfo = JSON.parse(JSON.stringify(draftMeta));
    clonedMeta.draft_id = newDraftId;
    clonedMeta.draft_name = newName;
    clonedMeta.draft_fold_path = newFolderPath.replace(/\\/g, '/');
    clonedMeta.tm_draft_create = nowUs;
    clonedMeta.tm_draft_modified = nowUs;

    await fs.writeFile(
      path.join(newFolderPath, 'draft_content.json'),
      JSON.stringify(clonedContent),
      'utf-8'
    );
    await fs.writeFile(
      path.join(newFolderPath, 'draft_meta_info.json'),
      JSON.stringify(clonedMeta),
      'utf-8'
    );

    // Register into root_meta_info.json
    const rootMeta = await CapCutPathResolver.readRootMeta();
    rootMeta.all_draft_store.unshift({
      draft_id: newDraftId,
      draft_name: newName,
      draft_fold_path: newFolderPath.replace(/\\/g, '/'),
      draft_json_file: path.join(newFolderPath, 'draft_content.json').replace(/\\/g, '/'),
      draft_cover: path.join(newFolderPath, 'draft_cover.jpg').replace(/\\/g, '/'),
      tm_duration: clonedContent.duration,
      tm_draft_create: nowUs,
      tm_draft_modified: nowUs,
      tm_draft_removed: 0,
      draft_root_path: draftsDir.replace(/\\/g, '/')
    });

    await CapCutPathResolver.writeRootMeta(rootMeta);

    const durSec = Math.round((clonedContent.duration / 1_000_000) * 100) / 100;
    return {
      id: newDraftId,
      name: newName,
      path: newFolderPath,
      durationSeconds: durSec,
      durationFormatted: MediaProbe.formatDuration(clonedContent.duration),
      resolution: `${clonedContent.canvas_config?.width}x${clonedContent.canvas_config?.height}`,
      ratio: clonedContent.canvas_config?.ratio || '9:16',
      fps: clonedContent.fps || 30,
      tracksCount: clonedContent.tracks.length,
      videoTracksCount: clonedContent.tracks.filter(t => t.type === 'video').length,
      audioTracksCount: clonedContent.tracks.filter(t => t.type === 'audio').length,
      textTracksCount: clonedContent.tracks.filter(t => t.type === 'text').length,
      isLocked: false
    };
  }

  /**
   * Deletes a CapCut project folder and removes it from root_meta_info.json.
   */
  public static async deleteProject(nameOrId: string, confirm = false): Promise<{ success: boolean; deletedPath: string }> {
    if (!confirm) {
      throw new Error(`Deletion requires explicit confirmation. Set confirm=true to delete project '${nameOrId}'.`);
    }

    const { folderPath, isLocked } = await CapCutPathResolver.findProjectDir(nameOrId);
    if (isLocked) {
      throw new Error(`Cannot delete project '${nameOrId}' because it is currently open in CapCut Desktop.`);
    }

    // Remove from root_meta_info
    const rootMeta = await CapCutPathResolver.readRootMeta();
    rootMeta.all_draft_store = rootMeta.all_draft_store.filter(
      d => d.draft_id !== nameOrId && d.draft_name !== nameOrId && path.resolve(d.draft_fold_path || '') !== folderPath
    );
    await CapCutPathResolver.writeRootMeta(rootMeta);

    // Delete folder from disk
    await fs.rm(folderPath, { recursive: true, force: true });

    return { success: true, deletedPath: folderPath };
  }

  /**
   * Inserts a video or image clip into a project track.
   */
  public static async addVideoClip(options: AddVideoClipOptions): Promise<{
    segmentId: string;
    materialId: string;
    startTimeSeconds: number;
    durationSeconds: number;
    projectDurationSeconds: number;
  }> {
    const { folderPath, isLocked } = await CapCutPathResolver.findProjectDir(options.projectNameOrId);
    if (isLocked) {
      throw new Error(`Project '${options.projectNameOrId}' is currently open in CapCut Desktop. Please return to the homepage or close CapCut before editing.`);
    }

    const resolvedFilePath = path.resolve(options.filePath);
    if (!existsSync(resolvedFilePath)) {
      throw new Error(`Media file not found at: ${resolvedFilePath}`);
    }

    // Probe media with ffprobe
    const probe = await MediaProbe.probeFile(resolvedFilePath);

    const { draftContent, draftMeta } = await this.getProject(options.projectNameOrId);

    // Find or create target video track
    const videoTracks = draftContent.tracks.filter(t => t.type === 'video');
    let targetTrack = videoTracks[options.trackIndex ?? 0];
    if (!targetTrack) {
      targetTrack = DraftBuilder.createTrack('video');
      draftContent.tracks.push(targetTrack);
    }

    // Determine timing
    const sourceStartUs = Math.round((options.sourceStartSeconds || 0) * 1_000_000);
    let clipDurationUs = options.durationSeconds
      ? Math.round(options.durationSeconds * 1_000_000)
      : probe.durationMicroseconds;

    if (probe.isImage && !options.durationSeconds) {
      clipDurationUs = 3_000_000; // default 3s for images
    }

    let startUs = 0;
    if (options.startTimeSeconds === 'auto_append' || options.startTimeSeconds === undefined) {
      if (targetTrack.segments.length > 0) {
        const lastSeg = targetTrack.segments[targetTrack.segments.length - 1];
        startUs = lastSeg.target_timerange.start + lastSeg.target_timerange.duration;
      } else {
        startUs = 0;
      }
    } else {
      startUs = Math.round(options.startTimeSeconds * 1_000_000);
    }

    const materialId = DraftBuilder.generateId();
    const videoMaterial = DraftBuilder.createVideoMaterial(
      materialId,
      resolvedFilePath,
      probe.durationMicroseconds,
      probe.width,
      probe.height,
      probe.hasAudio,
      probe.isImage
    );

    const segment = DraftBuilder.createVideoSegment(
      materialId,
      { start: startUs, duration: clipDurationUs },
      { start: sourceStartUs, duration: clipDurationUs },
      {
        scale: options.scale !== undefined ? { x: options.scale, y: options.scale } : undefined,
        rotation: options.rotation,
        transform: (options.x !== undefined || options.y !== undefined) ? { x: options.x ?? 0, y: options.y ?? 0 } : undefined,
        alpha: options.opacity
      }
    );

    // Add to draft content
    targetTrack.segments.push(segment);
    draftContent.materials.videos.push(videoMaterial);

    // Add to draft meta info
    if (!draftMeta.draft_materials) {
      draftMeta.draft_materials = [
        { type: 0, value: [] },
        { type: 1, value: [] },
        { type: 2, value: [] },
        { type: 3, value: [] },
        { type: 6, value: [] },
        { type: 7, value: [] }
      ];
    }

    let metaType0 = draftMeta.draft_materials.find(m => m.type === 0);
    if (!metaType0) {
      metaType0 = { type: 0, value: [] };
      draftMeta.draft_materials.push(metaType0);
    }

    metaType0.value.push({
      id: DraftBuilder.generateId().toLowerCase(),
      file_Path: resolvedFilePath.replace(/\\/g, '/'),
      duration: probe.durationMicroseconds,
      extra_info: path.basename(resolvedFilePath),
      metetype: probe.isImage ? 'photo' : 'video',
      width: probe.width,
      height: probe.height,
      create_time: Math.floor(Date.now() / 1000),
      import_time: Math.floor(Date.now() / 1000),
      roughcut_time_range: { start: 0, duration: probe.durationMicroseconds },
      sub_time_range: { start: -1, duration: -1 },
      type: 0
    });

    // Recalculate duration & save
    const newDurationUs = DraftBuilder.recalculateDuration(draftContent);
    draftContent.update_time = Date.now() * 1000;
    draftMeta.tm_duration = newDurationUs;
    draftMeta.tm_draft_modified = Date.now() * 1000;

    await fs.writeFile(path.join(folderPath, 'draft_content.json'), JSON.stringify(draftContent), 'utf-8');
    await fs.writeFile(path.join(folderPath, 'draft_meta_info.json'), JSON.stringify(draftMeta), 'utf-8');

    // Update root_meta_info duration
    const rootMeta = await CapCutPathResolver.readRootMeta();
    const item = rootMeta.all_draft_store.find(d => d.draft_id === draftContent.id || d.draft_name === draftContent.name);
    if (item) {
      item.tm_duration = newDurationUs;
      item.tm_draft_modified = Date.now() * 1000;
      await CapCutPathResolver.writeRootMeta(rootMeta);
    }

    return {
      segmentId: segment.id,
      materialId,
      startTimeSeconds: startUs / 1_000_000,
      durationSeconds: clipDurationUs / 1_000_000,
      projectDurationSeconds: newDurationUs / 1_000_000
    };
  }

  /**
   * Inserts an audio clip (music, sfx, voiceover) into an audio track.
   */
  public static async addAudioClip(options: AddAudioClipOptions): Promise<{
    segmentId: string;
    materialId: string;
    startTimeSeconds: number;
    durationSeconds: number;
    projectDurationSeconds: number;
  }> {
    const { folderPath, isLocked } = await CapCutPathResolver.findProjectDir(options.projectNameOrId);
    if (isLocked) {
      throw new Error(`Project '${options.projectNameOrId}' is currently open in CapCut Desktop.`);
    }

    const resolvedFilePath = path.resolve(options.filePath);
    if (!existsSync(resolvedFilePath)) {
      throw new Error(`Audio file not found at: ${resolvedFilePath}`);
    }

    const probe = await MediaProbe.probeFile(resolvedFilePath);
    const { draftContent, draftMeta } = await this.getProject(options.projectNameOrId);

    const audioTracks = draftContent.tracks.filter(t => t.type === 'audio');
    let targetTrack = audioTracks[options.trackIndex ?? 0];
    if (!targetTrack) {
      targetTrack = DraftBuilder.createTrack('audio');
      draftContent.tracks.push(targetTrack);
    }

    const sourceStartUs = Math.round((options.sourceStartSeconds || 0) * 1_000_000);
    const clipDurationUs = options.durationSeconds
      ? Math.round(options.durationSeconds * 1_000_000)
      : probe.durationMicroseconds;

    let startUs = 0;
    if (options.startTimeSeconds === 'auto_append' || options.startTimeSeconds === undefined) {
      if (targetTrack.segments.length > 0) {
        const lastSeg = targetTrack.segments[targetTrack.segments.length - 1];
        startUs = lastSeg.target_timerange.start + lastSeg.target_timerange.duration;
      } else {
        startUs = 0;
      }
    } else {
      startUs = Math.round(options.startTimeSeconds * 1_000_000);
    }

    const materialId = DraftBuilder.generateId();
    const audioMaterial = DraftBuilder.createAudioMaterial(
      materialId,
      resolvedFilePath,
      probe.durationMicroseconds
    );

    const segment = DraftBuilder.createAudioSegment(
      materialId,
      { start: startUs, duration: clipDurationUs },
      { start: sourceStartUs, duration: clipDurationUs },
      options.volume ?? 1.0
    );

    targetTrack.segments.push(segment);
    draftContent.materials.audios.push(audioMaterial);

    const newDurationUs = DraftBuilder.recalculateDuration(draftContent);
    draftContent.update_time = Date.now() * 1000;
    draftMeta.tm_duration = newDurationUs;
    draftMeta.tm_draft_modified = Date.now() * 1000;

    await fs.writeFile(path.join(folderPath, 'draft_content.json'), JSON.stringify(draftContent), 'utf-8');
    await fs.writeFile(path.join(folderPath, 'draft_meta_info.json'), JSON.stringify(draftMeta), 'utf-8');

    const rootMeta = await CapCutPathResolver.readRootMeta();
    const item = rootMeta.all_draft_store.find(d => d.draft_id === draftContent.id || d.draft_name === draftContent.name);
    if (item) {
      item.tm_duration = newDurationUs;
      item.tm_draft_modified = Date.now() * 1000;
      await CapCutPathResolver.writeRootMeta(rootMeta);
    }

    return {
      segmentId: segment.id,
      materialId,
      startTimeSeconds: startUs / 1_000_000,
      durationSeconds: clipDurationUs / 1_000_000,
      projectDurationSeconds: newDurationUs / 1_000_000
    };
  }

  /**
   * Adds a single styled text overlay or title to a text track.
   */
  public static async addText(options: AddTextOptions): Promise<{
    segmentId: string;
    materialId: string;
    startTimeSeconds: number;
    durationSeconds: number;
  }> {
    const { folderPath, isLocked } = await CapCutPathResolver.findProjectDir(options.projectNameOrId);
    if (isLocked) {
      throw new Error(`Project '${options.projectNameOrId}' is currently open in CapCut Desktop.`);
    }

    const { draftContent, draftMeta } = await this.getProject(options.projectNameOrId);

    const textTracks = draftContent.tracks.filter(t => t.type === 'text');
    let targetTrack = textTracks[options.trackIndex ?? 0];
    if (!targetTrack) {
      targetTrack = DraftBuilder.createTrack('text');
      draftContent.tracks.push(targetTrack);
    }

    const durationUs = Math.round((options.durationSeconds || 3.0) * 1_000_000);
    let startUs = 0;
    if (options.startTimeSeconds === 'auto_append' || options.startTimeSeconds === undefined) {
      if (targetTrack.segments.length > 0) {
        const lastSeg = targetTrack.segments[targetTrack.segments.length - 1];
        startUs = lastSeg.target_timerange.start + lastSeg.target_timerange.duration;
      } else {
        startUs = 0;
      }
    } else {
      startUs = Math.round(options.startTimeSeconds * 1_000_000);
    }

    const materialId = DraftBuilder.generateId();
    const textMaterial = DraftBuilder.createTextMaterial(materialId, options.text, {
      fontSize: options.fontSize,
      textColor: options.textColor,
      borderColor: options.borderColor,
      borderWidth: options.borderWidth,
      alignment: options.alignment
    });

    const segment = DraftBuilder.createTextSegment(
      materialId,
      { start: startUs, duration: durationUs },
      options.x ?? 0.0,
      options.y ?? -0.65
    );

    targetTrack.segments.push(segment);
    draftContent.materials.texts.push(textMaterial);

    const newDurationUs = DraftBuilder.recalculateDuration(draftContent);
    draftContent.update_time = Date.now() * 1000;
    draftMeta.tm_duration = newDurationUs;
    draftMeta.tm_draft_modified = Date.now() * 1000;

    await fs.writeFile(path.join(folderPath, 'draft_content.json'), JSON.stringify(draftContent), 'utf-8');
    await fs.writeFile(path.join(folderPath, 'draft_meta_info.json'), JSON.stringify(draftMeta), 'utf-8');

    return {
      segmentId: segment.id,
      materialId,
      startTimeSeconds: startUs / 1_000_000,
      durationSeconds: durationUs / 1_000_000
    };
  }

  /**
   * Batch adds subtitles / captions from an array of SubtitleItems or an SRT string/file.
   */
  public static async addSubtitles(options: AddSubtitlesOptions): Promise<{
    addedCount: number;
    trackId: string;
    totalProjectDurationSeconds: number;
  }> {
    const { folderPath, isLocked } = await CapCutPathResolver.findProjectDir(options.projectNameOrId);
    if (isLocked) {
      throw new Error(`Project '${options.projectNameOrId}' is currently open in CapCut Desktop.`);
    }

    let subtitleItems: SubtitleItem[] = options.subtitles || [];

    if (options.srtFilePath) {
      const srtRaw = await fs.readFile(path.resolve(options.srtFilePath), 'utf-8');
      subtitleItems = SrtParser.parse(srtRaw);
    } else if (options.srtContent) {
      subtitleItems = SrtParser.parse(options.srtContent);
    }

    if (subtitleItems.length === 0) {
      throw new Error('No subtitle items provided or SRT content was empty.');
    }

    const { draftContent, draftMeta } = await this.getProject(options.projectNameOrId);

    // Create dedicated text track for subtitles
    const subTrack = DraftBuilder.createTrack('text');
    subTrack.name = 'Subtitles';
    draftContent.tracks.push(subTrack);

    for (const item of subtitleItems) {
      const startUs = Math.round(item.startTimeSeconds * 1_000_000);
      const endUs = Math.round(item.endTimeSeconds * 1_000_000);
      const durationUs = Math.max(endUs - startUs, 100_000);

      const materialId = DraftBuilder.generateId();
      const textMaterial = DraftBuilder.createTextMaterial(materialId, item.text, {
        fontSize: options.fontSize || 10.0,
        textColor: options.textColor || '#ffffffff',
        borderColor: options.borderColor || '#000000ff',
        borderWidth: options.borderWidth ?? 0.08,
        alignment: 'center'
      });

      const segment = DraftBuilder.createTextSegment(
        materialId,
        { start: startUs, duration: durationUs },
        0.0,
        options.y ?? -0.72 // Lower third for subtitles
      );

      subTrack.segments.push(segment);
      draftContent.materials.texts.push(textMaterial);
    }

    const newDurationUs = DraftBuilder.recalculateDuration(draftContent);
    draftContent.update_time = Date.now() * 1000;
    draftMeta.tm_duration = newDurationUs;
    draftMeta.tm_draft_modified = Date.now() * 1000;

    await fs.writeFile(path.join(folderPath, 'draft_content.json'), JSON.stringify(draftContent), 'utf-8');
    await fs.writeFile(path.join(folderPath, 'draft_meta_info.json'), JSON.stringify(draftMeta), 'utf-8');

    return {
      addedCount: subtitleItems.length,
      trackId: subTrack.id,
      totalProjectDurationSeconds: newDurationUs / 1_000_000
    };
  }

  /**
   * Trims the start or duration of a specific segment.
   */
  public static async trimClip(
    projectNameOrId: string,
    segmentId: string,
    newStartSeconds?: number,
    newDurationSeconds?: number
  ): Promise<{ segmentId: string; newStart: number; newDuration: number }> {
    const { folderPath, isLocked } = await CapCutPathResolver.findProjectDir(projectNameOrId);
    if (isLocked) {
      throw new Error(`Project '${projectNameOrId}' is open in CapCut Desktop.`);
    }

    const { draftContent, draftMeta } = await this.getProject(projectNameOrId);

    let targetSegment = null;
    for (const track of draftContent.tracks) {
      const found = track.segments.find(s => s.id === segmentId);
      if (found) {
        targetSegment = found;
        break;
      }
    }

    if (!targetSegment) {
      throw new Error(`Segment '${segmentId}' not found in project.`);
    }

    if (newStartSeconds !== undefined) {
      targetSegment.target_timerange.start = Math.round(newStartSeconds * 1_000_000);
    }
    if (newDurationSeconds !== undefined) {
      targetSegment.target_timerange.duration = Math.round(newDurationSeconds * 1_000_000);
      if (targetSegment.source_timerange) {
        targetSegment.source_timerange.duration = Math.round(newDurationSeconds * 1_000_000);
      }
    }

    DraftBuilder.recalculateDuration(draftContent);
    await fs.writeFile(path.join(folderPath, 'draft_content.json'), JSON.stringify(draftContent), 'utf-8');
    await fs.writeFile(path.join(folderPath, 'draft_meta_info.json'), JSON.stringify(draftMeta), 'utf-8');

    return {
      segmentId,
      newStart: targetSegment.target_timerange.start / 1_000_000,
      newDuration: targetSegment.target_timerange.duration / 1_000_000
    };
  }

  /**
   * Removes a segment from a track.
   */
  public static async removeClip(projectNameOrId: string, segmentId: string): Promise<{ success: boolean }> {
    const { folderPath, isLocked } = await CapCutPathResolver.findProjectDir(projectNameOrId);
    if (isLocked) {
      throw new Error(`Project '${projectNameOrId}' is open in CapCut Desktop.`);
    }

    const { draftContent, draftMeta } = await this.getProject(projectNameOrId);

    let removed = false;
    for (const track of draftContent.tracks) {
      const idx = track.segments.findIndex(s => s.id === segmentId);
      if (idx !== -1) {
        track.segments.splice(idx, 1);
        removed = true;
        break;
      }
    }

    if (!removed) {
      throw new Error(`Segment '${segmentId}' not found in project.`);
    }

    DraftBuilder.recalculateDuration(draftContent);
    await fs.writeFile(path.join(folderPath, 'draft_content.json'), JSON.stringify(draftContent), 'utf-8');
    await fs.writeFile(path.join(folderPath, 'draft_meta_info.json'), JSON.stringify(draftMeta), 'utf-8');

    return { success: true };
  }

  /**
   * Sets transformation (scale, rotation, position x/y, opacity) of a clip.
   */
  public static async setClipTransform(
    projectNameOrId: string,
    segmentId: string,
    transform: {
      scale?: number;
      rotation?: number;
      x?: number;
      y?: number;
      alpha?: number;
    }
  ): Promise<{ segmentId: string }> {
    const { folderPath, isLocked } = await CapCutPathResolver.findProjectDir(projectNameOrId);
    if (isLocked) {
      throw new Error(`Project '${projectNameOrId}' is open in CapCut Desktop.`);
    }

    const { draftContent } = await this.getProject(projectNameOrId);

    let targetSegment = null;
    for (const track of draftContent.tracks) {
      const found = track.segments.find(s => s.id === segmentId);
      if (found) {
        targetSegment = found;
        break;
      }
    }

    if (!targetSegment) {
      throw new Error(`Segment '${segmentId}' not found in project.`);
    }

    if (!targetSegment.clip) {
      targetSegment.clip = {
        scale: { x: 1.0, y: 1.0 },
        rotation: 0.0,
        transform: { x: 0.0, y: 0.0 },
        flip: { vertical: false, horizontal: false },
        alpha: 1.0
      };
    }

    if (transform.scale !== undefined) {
      targetSegment.clip.scale.x = transform.scale;
      targetSegment.clip.scale.y = transform.scale;
    }
    if (transform.rotation !== undefined) {
      targetSegment.clip.rotation = transform.rotation;
    }
    if (transform.x !== undefined) {
      targetSegment.clip.transform.x = transform.x;
    }
    if (transform.y !== undefined) {
      targetSegment.clip.transform.y = transform.y;
    }
    if (transform.alpha !== undefined) {
      targetSegment.clip.alpha = transform.alpha;
    }

    await fs.writeFile(path.join(folderPath, 'draft_content.json'), JSON.stringify(draftContent), 'utf-8');
    return { segmentId };
  }

  /**
   * Adds a transition (e.g. Dissolve, Fade to Black, Zoom In) to a video segment.
   */
  public static async addTransition(options: AddTransitionOptions): Promise<{ transitionId: string; segmentId: string; name: string }> {
    const { folderPath, isLocked } = await CapCutPathResolver.findProjectDir(options.projectNameOrId);
    if (isLocked) {
      throw new Error(`Project '${options.projectNameOrId}' is open in CapCut Desktop.`);
    }

    const { draftContent } = await this.getProject(options.projectNameOrId);

    let targetSegment = null;
    for (const track of draftContent.tracks) {
      const found = track.segments.find(s => s.id === options.segmentId);
      if (found) {
        targetSegment = found;
        break;
      }
    }

    if (!targetSegment) {
      throw new Error(`Segment '${options.segmentId}' not found in project.`);
    }

    const transitionId = DraftBuilder.generateId();
    const transName = options.transitionName || 'Dissolve';
    const durationUs = Math.round((options.durationSeconds || 0.5) * 1_000_000);

    const transMaterial = DraftBuilder.createTransitionMaterial(transitionId, transName, durationUs);
    if (!draftContent.materials.transitions) {
      draftContent.materials.transitions = [];
    }
    (draftContent.materials.transitions as unknown[]).push(transMaterial);

    if (!targetSegment.extra_material_refs) {
      targetSegment.extra_material_refs = [];
    }
    targetSegment.extra_material_refs.push(transitionId);

    await fs.writeFile(path.join(folderPath, 'draft_content.json'), JSON.stringify(draftContent), 'utf-8');
    return { transitionId, segmentId: options.segmentId, name: transName };
  }

  /**
   * Adds an animation keyframe to a video segment.
   */
  public static async addKeyframe(options: AddKeyframeOptions): Promise<{ keyframeId: string; segmentId: string }> {
    const { folderPath, isLocked } = await CapCutPathResolver.findProjectDir(options.projectNameOrId);
    if (isLocked) {
      throw new Error(`Project '${options.projectNameOrId}' is open in CapCut Desktop.`);
    }

    const { draftContent } = await this.getProject(options.projectNameOrId);

    let targetSegment = null;
    for (const track of draftContent.tracks) {
      const found = track.segments.find(s => s.id === options.segmentId);
      if (found) {
        targetSegment = found;
        break;
      }
    }

    if (!targetSegment) {
      throw new Error(`Segment '${options.segmentId}' not found in project.`);
    }

    const keyframeId = DraftBuilder.generateId();
    const timeOffsetUs = Math.round(options.timeOffsetSeconds * 1_000_000);
    const kf = DraftBuilder.createKeyframe(keyframeId, options.property, timeOffsetUs, options.value);

    if (!draftContent.keyframes) {
      draftContent.keyframes = { videos: [] };
    }
    const kfVideos = (draftContent.keyframes as Record<string, unknown[]>).videos;
    if (Array.isArray(kfVideos)) {
      kfVideos.push(kf);
    }

    if (!targetSegment.keyframe_refs) {
      targetSegment.keyframe_refs = [];
    }
    (targetSegment.keyframe_refs as string[]).push(keyframeId);

    await fs.writeFile(path.join(folderPath, 'draft_content.json'), JSON.stringify(draftContent), 'utf-8');
    return { keyframeId, segmentId: options.segmentId };
  }

  /**
   * Adds a sticker / graphic element to the project.
   */
  public static async addSticker(options: AddStickerOptions): Promise<{ segmentId: string; materialId: string }> {
    const { folderPath, isLocked } = await CapCutPathResolver.findProjectDir(options.projectNameOrId);
    if (isLocked) {
      throw new Error(`Project '${options.projectNameOrId}' is open in CapCut Desktop.`);
    }

    const { draftContent, draftMeta } = await this.getProject(options.projectNameOrId);

    const stickerTracks = draftContent.tracks.filter(t => t.type === 'sticker');
    let targetTrack = stickerTracks[options.trackIndex ?? 0];
    if (!targetTrack) {
      targetTrack = {
        id: DraftBuilder.generateId(),
        type: 'sticker',
        segments: [],
        flag: 0,
        attribute: 0,
        name: 'Stickers',
        is_default_name: true
      };
      draftContent.tracks.push(targetTrack);
    }

    const durationUs = Math.round((options.durationSeconds || 3.0) * 1_000_000);
    let startUs = 0;
    if (options.startTimeSeconds === 'auto_append' || options.startTimeSeconds === undefined) {
      if (targetTrack.segments.length > 0) {
        const lastSeg = targetTrack.segments[targetTrack.segments.length - 1];
        startUs = lastSeg.target_timerange.start + lastSeg.target_timerange.duration;
      }
    } else {
      startUs = Math.round(options.startTimeSeconds * 1_000_000);
    }

    const materialId = DraftBuilder.generateId();
    const stickerMaterial = {
      id: materialId,
      name: options.stickerName,
      type: 'sticker',
      resource_id: DraftBuilder.generateHexId()
    };

    if (!draftContent.materials.stickers) {
      draftContent.materials.stickers = [];
    }
    (draftContent.materials.stickers as unknown[]).push(stickerMaterial);

    const segment = DraftBuilder.createStickerSegment(
      materialId,
      { start: startUs, duration: durationUs },
      options.x ?? 0.0,
      options.y ?? 0.0,
      options.scale ?? 1.0
    );

    targetTrack.segments.push(segment);

    const newDurationUs = DraftBuilder.recalculateDuration(draftContent);
    draftContent.update_time = Date.now() * 1000;
    draftMeta.tm_duration = newDurationUs;

    await fs.writeFile(path.join(folderPath, 'draft_content.json'), JSON.stringify(draftContent), 'utf-8');
    await fs.writeFile(path.join(folderPath, 'draft_meta_info.json'), JSON.stringify(draftMeta), 'utf-8');

    return { segmentId: segment.id, materialId };
  }

  /**
   * Generates a fast proxy preview video (.mp4) using ffmpeg directly from project timeline assets.
   */
  public static async generatePreview(options: GeneratePreviewOptions): Promise<{ outputPath: string; durationSeconds: number }> {
    const { folderPath } = await CapCutPathResolver.findProjectDir(options.projectNameOrId);
    const { draftContent } = await this.getProject(options.projectNameOrId);

    return await PreviewRenderer.renderDraft(draftContent, folderPath, options);
  }

  /**
   * Splits a clip/segment into two linked parts at an exact timeline timestamp.
   */
  public static async splitClip(options: SplitClipOptions): Promise<{
    firstSegmentId: string;
    secondSegmentId: string;
    splitTimeSeconds: number;
  }> {
    const { folderPath, isLocked } = await CapCutPathResolver.findProjectDir(options.projectNameOrId);
    if (isLocked) {
      throw new Error(`Project '${options.projectNameOrId}' is open in CapCut Desktop.`);
    }

    const { draftContent, draftMeta } = await this.getProject(options.projectNameOrId);

    let targetTrack = null;
    let targetSegmentIndex = -1;
    for (const track of draftContent.tracks) {
      const idx = track.segments.findIndex(s => s.id === options.segmentId);
      if (idx !== -1) {
        targetTrack = track;
        targetSegmentIndex = idx;
        break;
      }
    }

    if (!targetTrack || targetSegmentIndex === -1) {
      throw new Error(`Segment '${options.segmentId}' not found in project.`);
    }

    const targetSegment = targetTrack.segments[targetSegmentIndex];
    const splitTimeUs = Math.round(options.splitTimeSeconds * 1_000_000);
    const newSegmentId = DraftBuilder.generateId();

    const { firstSegment, secondSegment } = DraftBuilder.splitSegment(targetSegment, splitTimeUs, newSegmentId);
    targetTrack.segments.splice(targetSegmentIndex + 1, 0, secondSegment);

    DraftBuilder.recalculateDuration(draftContent);
    draftContent.update_time = Date.now() * 1000;
    draftMeta.tm_duration = draftContent.duration;

    await fs.writeFile(path.join(folderPath, 'draft_content.json'), JSON.stringify(draftContent), 'utf-8');
    await fs.writeFile(path.join(folderPath, 'draft_meta_info.json'), JSON.stringify(draftMeta), 'utf-8');

    return {
      firstSegmentId: firstSegment.id,
      secondSegmentId: secondSegment.id,
      splitTimeSeconds: options.splitTimeSeconds
    };
  }

  /**
   * Sets the playback speed and pitch preservation of a clip.
   */
  public static async setClipSpeed(options: SetClipSpeedOptions): Promise<{
    segmentId: string;
    speed: number;
    newDurationSeconds: number;
  }> {
    const { folderPath, isLocked } = await CapCutPathResolver.findProjectDir(options.projectNameOrId);
    if (isLocked) {
      throw new Error(`Project '${options.projectNameOrId}' is open in CapCut Desktop.`);
    }

    if (options.speed <= 0) {
      throw new Error(`Speed multiplier must be greater than 0.`);
    }

    const { draftContent, draftMeta } = await this.getProject(options.projectNameOrId);

    let targetSegment = null;
    for (const track of draftContent.tracks) {
      const found = track.segments.find(s => s.id === options.segmentId);
      if (found) {
        targetSegment = found;
        break;
      }
    }

    if (!targetSegment) {
      throw new Error(`Segment '${options.segmentId}' not found in project.`);
    }

    targetSegment.speed = options.speed;
    targetSegment.is_tone_modify = options.preservePitch !== false;

    if (targetSegment.source_timerange) {
      targetSegment.target_timerange.duration = Math.round(targetSegment.source_timerange.duration / options.speed);
    }

    if (!draftContent.materials.speeds) {
      draftContent.materials.speeds = [];
    }
    const speedId = DraftBuilder.generateId();
    const speedMaterial = DraftBuilder.createSpeedMaterial(speedId, options.speed);
    (draftContent.materials.speeds as SpeedMaterial[]).push(speedMaterial);

    if (!targetSegment.extra_material_refs) {
      targetSegment.extra_material_refs = [];
    }
    targetSegment.extra_material_refs.push(speedId);

    DraftBuilder.recalculateDuration(draftContent);
    draftContent.update_time = Date.now() * 1000;
    draftMeta.tm_duration = draftContent.duration;

    await fs.writeFile(path.join(folderPath, 'draft_content.json'), JSON.stringify(draftContent), 'utf-8');
    await fs.writeFile(path.join(folderPath, 'draft_meta_info.json'), JSON.stringify(draftMeta), 'utf-8');

    return {
      segmentId: targetSegment.id,
      speed: options.speed,
      newDurationSeconds: targetSegment.target_timerange.duration / 1_000_000
    };
  }

  /**
   * Adds fade-in and/or fade-out envelopes to an audio clip.
   */
  public static async addAudioFade(options: AddAudioFadeOptions): Promise<{
    segmentId: string;
    fadeId: string;
    fadeInSeconds: number;
    fadeOutSeconds: number;
  }> {
    const { folderPath, isLocked } = await CapCutPathResolver.findProjectDir(options.projectNameOrId);
    if (isLocked) {
      throw new Error(`Project '${options.projectNameOrId}' is open in CapCut Desktop.`);
    }

    const { draftContent } = await this.getProject(options.projectNameOrId);

    let targetSegment = null;
    for (const track of draftContent.tracks) {
      const found = track.segments.find(s => s.id === options.segmentId);
      if (found) {
        targetSegment = found;
        break;
      }
    }

    if (!targetSegment) {
      throw new Error(`Segment '${options.segmentId}' not found in project.`);
    }

    const fadeInUs = Math.round((options.fadeInSeconds || 0) * 1_000_000);
    const fadeOutUs = Math.round((options.fadeOutSeconds || 0) * 1_000_000);
    const fadeId = DraftBuilder.generateId();

    const fadeMaterial = DraftBuilder.createAudioFadeMaterial(fadeId, fadeInUs, fadeOutUs);
    if (!draftContent.materials.audio_fades) {
      draftContent.materials.audio_fades = [];
    }
    (draftContent.materials.audio_fades as AudioFadeMaterial[]).push(fadeMaterial);

    if (!targetSegment.extra_material_refs) {
      targetSegment.extra_material_refs = [];
    }
    targetSegment.extra_material_refs.push(fadeId);

    await fs.writeFile(path.join(folderPath, 'draft_content.json'), JSON.stringify(draftContent), 'utf-8');

    return {
      segmentId: targetSegment.id,
      fadeId,
      fadeInSeconds: options.fadeInSeconds || 0,
      fadeOutSeconds: options.fadeOutSeconds || 0
    };
  }

  /**
   * Injects an Aeovisuals-calibrated viral caption with -1.0 kerning, 26/26 diffuse ambient shadow,
   * power word contrast, and optional Quad Ease hover-up keyframe pop.
   */
  public static async addViralCaption(options: AddViralCaptionOptions): Promise<{
    segmentId: string;
    materialId: string;
    text: string;
  }> {
    const { folderPath, isLocked } = await CapCutPathResolver.findProjectDir(options.projectNameOrId);
    if (isLocked) {
      throw new Error(`Project '${options.projectNameOrId}' is open in CapCut Desktop.`);
    }

    const { draftContent, draftMeta } = await this.getProject(options.projectNameOrId);

    const textTracks = draftContent.tracks.filter(t => t.type === 'text');
    let targetTrack = textTracks[options.trackIndex ?? 0];
    if (!targetTrack) {
      targetTrack = {
        id: DraftBuilder.generateId(),
        type: 'text',
        segments: [],
        flag: 0,
        attribute: 0,
        name: 'Viral Captions',
        is_default_name: true
      };
      draftContent.tracks.push(targetTrack);
    }

    const durationUs = Math.round((options.durationSeconds || 3.0) * 1_000_000);
    let startUs = 0;
    if (options.startTimeSeconds === 'auto_append' || options.startTimeSeconds === undefined) {
      if (targetTrack.segments.length > 0) {
        const lastSeg = targetTrack.segments[targetTrack.segments.length - 1];
        startUs = lastSeg.target_timerange.start + lastSeg.target_timerange.duration;
      }
    } else {
      startUs = Math.round(options.startTimeSeconds * 1_000_000);
    }

    const materialId = DraftBuilder.generateId();
    const textMaterial = DraftBuilder.createViralCaptionMaterial(materialId, options.text, {
      fontSize: options.fontSize || 14.0,
      fontFamily: options.fontFamily || 'Montserrat',
      accentColor: options.accentColor || '#FF1E27',
      powerWords: options.powerWords || []
    });

    draftContent.materials.texts.push(textMaterial);

    const targetY = options.y ?? -0.65;
    const segment = DraftBuilder.createTextSegment(
      materialId,
      { start: startUs, duration: durationUs },
      options.x ?? 0.0,
      targetY
    );

    if (options.enableHoverPop !== false) {
      if (!draftContent.keyframes) {
        draftContent.keyframes = { texts: [], videos: [] };
      }
      const kfList = (draftContent.keyframes as Record<string, unknown[]>).texts || [];
      (draftContent.keyframes as Record<string, unknown[]>).texts = kfList;

      const kfY0 = DraftBuilder.createKeyframe(DraftBuilder.generateId(), 'y', 0, targetY - 0.035);
      const kfY1 = DraftBuilder.createKeyframe(DraftBuilder.generateId(), 'y', 83_333, targetY);
      const kfA0 = DraftBuilder.createKeyframe(DraftBuilder.generateId(), 'alpha', 0, 0.0);
      const kfA1 = DraftBuilder.createKeyframe(DraftBuilder.generateId(), 'alpha', 83_333, 1.0);

      kfList.push(kfY0, kfY1, kfA0, kfA1);

      if (!segment.keyframe_refs) {
        segment.keyframe_refs = [];
      }
      (segment.keyframe_refs as string[]).push(kfY0.id, kfY1.id, kfA0.id, kfA1.id);
    }

    targetTrack.segments.push(segment);

    const newDurationUs = DraftBuilder.recalculateDuration(draftContent);
    draftContent.update_time = Date.now() * 1000;
    draftMeta.tm_duration = newDurationUs;

    await fs.writeFile(path.join(folderPath, 'draft_content.json'), JSON.stringify(draftContent), 'utf-8');
    await fs.writeFile(path.join(folderPath, 'draft_meta_info.json'), JSON.stringify(draftMeta), 'utf-8');

    return { segmentId: segment.id, materialId, text: options.text };
  }

  /**
   * One-step orchestrator: builds a CapCut draft around a pre-rendered master video plate,
   * synchronizes multi-track audio, and injects editable subtitles.
   */
  public static async createVideoBridge(options: CreateVideoBridgeOptions): Promise<{
    projectName: string;
    summary: ProjectSummary;
    videoSegmentId: string;
  }> {
    await this.createProject({
      name: options.projectName,
      ratio: options.ratio || '9:16',
      fps: options.fps || 60.0
    });

    const videoRes = await this.addVideoClip({
      projectNameOrId: options.projectName,
      filePath: options.videoPlatePath,
      trackIndex: 0,
      startTimeSeconds: 0
    });

    if (options.audioTracks && options.audioTracks.length > 0) {
      for (const audio of options.audioTracks) {
        await this.addAudioClip({
          projectNameOrId: options.projectName,
          filePath: audio.filePath,
          trackIndex: audio.trackIndex ?? 0,
          startTimeSeconds: 0,
          volume: audio.volume ?? 1.0
        });
      }
    }

    if (options.subtitlesSrtPath) {
      await this.addSubtitles({
        projectNameOrId: options.projectName,
        srtFilePath: options.subtitlesSrtPath,
        fontSize: 11.0,
        y: -0.68
      });
    }

    const { summary } = await this.getProject(options.projectName);
    return {
      projectName: options.projectName,
      summary,
      videoSegmentId: videoRes.segmentId
    };
  }

  /**
   * Convenience helper to drop transient sound effects (whoosh, pop, click) at exact timestamps.
   */
  public static async addSoundEffect(options: AddSoundEffectOptions): Promise<{
    segmentId: string;
    timestampSeconds: number;
    filePath: string;
  }> {
    const res = await this.addAudioClip({
      projectNameOrId: options.projectNameOrId,
      filePath: options.sfxFilePath,
      trackIndex: options.trackIndex ?? 1,
      startTimeSeconds: options.timestampSeconds,
      volume: options.volume ?? 0.7
    });

    return {
      segmentId: res.segmentId,
      timestampSeconds: options.timestampSeconds,
      filePath: options.sfxFilePath
    };
  }
}



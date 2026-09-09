/**
 * 향 지도 데이터 타입 — 제안입니다.
 *
 * 실제 API 응답 모양은 백엔드 담당자분이 정하십니다. 이 파일은 "데이터에 어떤
 * 필드가 어떤 타입으로 들어 있는지" 를 보여드리려고 만든 것이니, 필드 이름이나
 * 구조는 프로젝트 규약에 맞게 바꿔 쓰셔도 됩니다.
 *
 * 값의 범위와 개수는 실제 데이터에서 확인한 것입니다.
 */

/** 향 계열 9개. 이 문자열이 안정적인 키다 (숫자 id 는 배열 위치라 밀릴 수 있다). */
export type FamilyKey =
  | 'CITRUS' | 'FRUITY' | 'FLORAL' | 'GREEN' | 'AQUATIC'
  | 'WOODY' | 'AMBER' | 'GOURMAND' | 'MUSK';

/**
 * 좌표. 두 가지 공간이 섞여 있으니 구분해야 한다.
 *  - 향수 좌표(MapPoint.x, y): 0 ~ 1
 *  - 폴리곤 · 해안선 · 라벨 앵커: 지형 파일의 bounds 공간. 음수가 나온다
 */
export interface Coord { x: number; y: number }

/** 폴리곤은 고리의 배열이다. 고리는 [x, y] 점의 배열. */
export type Ring = [number, number][];
export type Polygon = Ring[];

export interface ScentFamily {
  key: FamilyKey;
  nameKo: string;
  displayOrder: number;      // 0 ~ 8
  perfumeCount: number;      // 이 계열이 1순위인 향수 수. 합 200
  anchor: Coord;             // 라벨을 놓을 위치
  polygon: Polygon;          // 고리 1 ~ 5개
}

export interface PerfumeFamily {
  key: FamilyKey;
  /**
   * 그 향수 안에서 이 계열이 차지하는 비중. 실측 0.20 ~ 0.8224.
   * 향수별 합은 1.0 이 아닐 수 있다 (재정규화하지 않았다).
   * 1 - 합 을 "기타" 로 읽으면 안 된다.
   */
  weight: number;
}

export interface MapPoint {
  fragranticaId: number;
  brand: string;
  name: string;
  x: number;                 // 0 ~ 1
  y: number;                 // 0 ~ 0.83056. bounds 를 읽어 쓰고 하드코딩하지 말 것
  families: PerfumeFamily[]; // 1 ~ 3개. weight 내림차순
  koreaRank: number;         // 1 ~ 200
}

export interface Neighbor {
  fragranticaId: number;
  /** 향 성분으로 계산한 유사도. 지도 위 거리가 아니다. 실측 0.2021 ~ 0.7797 */
  similarity: number;
  rank: number;              // 1 = 가장 닮은
}

export interface Bounds { x_min: number; x_max: number; y_min: number; y_max: number }

export interface ScentMap {
  mapVersion: string;
  bounds: Bounds;
  terrainUrl: string;
  families: ScentFamily[];   // 9개
  points: MapPoint[];        // 200개
}

/** 지도 배경. 정적 파일로 한 번 받아 캐시하면 된다. */
export interface ScentMapTerrain {
  gridWidth: number;         // 128 (상수)
  gridHeight: number;        // 108. 좌표에서 파생되므로 하드코딩하지 말 것
  bounds: Bounds;            // 향수 좌표보다 넓다. 음수 포함
  density: {
    /** gridWidth * gridHeight 개. row 0 이 y_min(아래)이다 */
    values: number[];
    /** 이 값보다 큰 칸이 땅이다 */
    seaLevel: number;
    valueRange: [number, number];   // [0, 255]. 여기서 255 는 최대 밀도지 바다가 아니다
  };
  familyGrid: {
    /** gridWidth * gridHeight 개. 값은 idToKey 의 인덱스, 255 는 바다 */
    values: number[];
    seaValue: 255;
    idToKey: FamilyKey[];
  };
  contours: { level: number; polygons: Polygon }[];
}

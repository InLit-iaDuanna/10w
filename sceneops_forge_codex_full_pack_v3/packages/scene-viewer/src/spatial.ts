export type Vector3 = readonly [number, number, number];

export type Matrix4 = readonly [
  number,
  number,
  number,
  number,
  number,
  number,
  number,
  number,
  number,
  number,
  number,
  number,
  number,
  number,
  number,
  number,
];

export const IDENTITY_MATRIX4: Matrix4 = Object.freeze([
  1, 0, 0, 0,
  0, 1, 0, 0,
  0, 0, 1, 0,
  0, 0, 0, 1,
]);

export class SpatialMathError extends Error {
  readonly code: 'INVALID_MATRIX' | 'SINGULAR_MATRIX' | 'INVALID_VECTOR';

  constructor(
    code: 'INVALID_MATRIX' | 'SINGULAR_MATRIX' | 'INVALID_VECTOR',
    message: string,
  ) {
    super(message);
    this.name = 'SpatialMathError';
    this.code = code;
  }
}

export function createMatrix4(values: readonly number[]): Matrix4 {
  if (values.length !== 16 || values.some((value) => !Number.isFinite(value))) {
    throw new SpatialMathError('INVALID_MATRIX', 'Matrix4 requires exactly 16 finite values.');
  }

  return Object.freeze([...values]) as unknown as Matrix4;
}

export function cloneMatrix4(matrix: Matrix4): Matrix4 {
  return createMatrix4(matrix);
}

export function multiplyMatrix4(left: Matrix4, right: Matrix4): Matrix4 {
  const result = new Array<number>(16).fill(0);

  for (let column = 0; column < 4; column += 1) {
    for (let row = 0; row < 4; row += 1) {
      let value = 0;
      for (let term = 0; term < 4; term += 1) {
        value += left[term * 4 + row]! * right[column * 4 + term]!;
      }
      result[column * 4 + row] = value;
    }
  }

  return createMatrix4(result);
}

export function invertMatrix4(matrix: Matrix4): Matrix4 {
  const rows = Array.from({ length: 4 }, (_, row) => {
    const values = new Array<number>(8).fill(0);
    for (let column = 0; column < 4; column += 1) {
      values[column] = matrix[column * 4 + row]!;
      values[column + 4] = row === column ? 1 : 0;
    }
    return values;
  });

  for (let pivotColumn = 0; pivotColumn < 4; pivotColumn += 1) {
    let pivotRow = pivotColumn;
    for (let row = pivotColumn + 1; row < 4; row += 1) {
      if (Math.abs(rows[row]![pivotColumn]!) > Math.abs(rows[pivotRow]![pivotColumn]!)) {
        pivotRow = row;
      }
    }

    if (Math.abs(rows[pivotRow]![pivotColumn]!) <= 1e-12) {
      throw new SpatialMathError('SINGULAR_MATRIX', 'Matrix cannot be inverted.');
    }

    [rows[pivotColumn], rows[pivotRow]] = [rows[pivotRow]!, rows[pivotColumn]!];
    const pivot = rows[pivotColumn]![pivotColumn]!;
    rows[pivotColumn] = rows[pivotColumn]!.map((value) => value / pivot);

    for (let row = 0; row < 4; row += 1) {
      if (row === pivotColumn) continue;
      const factor = rows[row]![pivotColumn]!;
      rows[row] = rows[row]!.map(
        (value, column) => value - factor * rows[pivotColumn]![column]!,
      );
    }
  }

  const inverse = new Array<number>(16).fill(0);
  for (let row = 0; row < 4; row += 1) {
    for (let column = 0; column < 4; column += 1) {
      inverse[column * 4 + row] = rows[row]![column + 4]!;
    }
  }
  return createMatrix4(inverse);
}

export function transformPoint(matrix: Matrix4, point: Vector3): Vector3 {
  assertVector3(point, 'Point');
  const [x, y, z] = point;
  const w = matrix[3]! * x + matrix[7]! * y + matrix[11]! * z + matrix[15]!;
  if (Math.abs(w) <= 1e-12) {
    throw new SpatialMathError('INVALID_VECTOR', 'Point transforms to a zero homogeneous w.');
  }

  return Object.freeze([
    (matrix[0]! * x + matrix[4]! * y + matrix[8]! * z + matrix[12]!) / w,
    (matrix[1]! * x + matrix[5]! * y + matrix[9]! * z + matrix[13]!) / w,
    (matrix[2]! * x + matrix[6]! * y + matrix[10]! * z + matrix[14]!) / w,
  ]);
}

export function transformDirection(matrix: Matrix4, direction: Vector3): Vector3 {
  assertVector3(direction, 'Direction');
  const [x, y, z] = direction;
  return Object.freeze([
    matrix[0]! * x + matrix[4]! * y + matrix[8]! * z,
    matrix[1]! * x + matrix[5]! * y + matrix[9]! * z,
    matrix[2]! * x + matrix[6]! * y + matrix[10]! * z,
  ]);
}

export function transformNormal(matrix: Matrix4, normal: Vector3): Vector3 {
  assertVector3(normal, 'Normal');
  const inverse = invertMatrix4(matrix);
  const [x, y, z] = normal;
  return normalizeVector3([
    inverse[0]! * x + inverse[1]! * y + inverse[2]! * z,
    inverse[4]! * x + inverse[5]! * y + inverse[6]! * z,
    inverse[8]! * x + inverse[9]! * y + inverse[10]! * z,
  ]);
}

export function normalizeVector3(vector: Vector3): Vector3 {
  assertVector3(vector, 'Vector');
  const length = Math.hypot(...vector);
  if (length <= 1e-12) {
    throw new SpatialMathError('INVALID_VECTOR', 'Cannot normalize a zero-length vector.');
  }
  return Object.freeze([vector[0] / length, vector[1] / length, vector[2] / length]);
}

function assertVector3(vector: Vector3, label: string): void {
  if (vector.some((value) => !Number.isFinite(value))) {
    throw new SpatialMathError('INVALID_VECTOR', `${label} requires three finite values.`);
  }
}

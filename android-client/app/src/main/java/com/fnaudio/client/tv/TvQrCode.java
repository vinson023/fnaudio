package com.fnaudio.client.tv;

/**
 * Minimal QR encoder for the pairing code: byte mode, error correction M,
 * versions 1-6.
 *
 * <p>Why not a library: the television build runs {@code --offline} against a
 * pinned Gradle cache, and adding ZXing would mean one network sync that every
 * future machine has to repeat. The plan preferred ZXing for good reason - a
 * hand-written encoder that is subtly wrong produces a picture that scans as
 * nothing - so this implementation is checked module-for-module against a
 * reference encoder in tests and never guesses: any payload over 106 bytes, or
 * any version whose block layout is uneven, is rejected rather than encoded
 * approximately.
 *
 * <p>Only what a pairing URI needs is implemented. Alphanumeric/kanji modes,
 * versions 7+ (version info blocks) and uneven block groups are deliberately
 * absent: {@code fnaudio://pair?v=1&h=192.168.5.141&p=42001&c=482913} is about
 * 50 bytes, which fits version 4-M with room to spare.
 */
final class TvQrCode {
    /** Level M: (ec codewords per block, block count, data codewords per block). */
    private static final int[][] LEVEL_M = {
            {10, 1, 16},   // version 1
            {16, 1, 28},   // version 2
            {26, 1, 44},   // version 3
            {18, 2, 32},   // version 4
            {24, 2, 43},   // version 5
            {16, 4, 27},   // version 6
    };

    /** Alignment pattern centres per version; version 1 has none. */
    private static final int[][] ALIGNMENT = {
            {},
            {6, 18},
            {6, 22},
            {6, 26},
            {6, 30},
            {6, 34},
    };

    private TvQrCode() {
    }

    /**
     * Encodes {@code text} and picks the mask with the lowest penalty.
     *
     * @throws IllegalArgumentException when the payload does not fit version 6-M
     */
    static boolean[][] encode(String text) {
        int bestMask = 0;
        boolean[][] best = null;
        int bestScore = Integer.MAX_VALUE;
        for (int mask = 0; mask < 8; mask++) {
            boolean[][] candidate = encode(text, mask);
            int score = penalty(candidate);
            if (score < bestScore) {
                bestScore = score;
                bestMask = mask;
                best = candidate;
            }
        }
        if (best == null) throw new IllegalArgumentException("payload too large");
        return best;
    }

    /** Encodes with an explicit mask; used by the module-for-module tests. */
    static boolean[][] encode(String text, int mask) {
        byte[] payload = text.getBytes(java.nio.charset.StandardCharsets.ISO_8859_1);
        if (payload.length > 106) {
            throw new IllegalArgumentException("payload exceeds version 6-M capacity");
        }
        int version = 1;
        while (version <= 6 && dataCodewords(version) < payload.length + 2) version++;
        if (version > 6) throw new IllegalArgumentException("payload exceeds version 6-M capacity");

        byte[] codewords = buildCodewords(payload, version);
        boolean[][] matrix = new boolean[size(version)][size(version)];
        boolean[][] function = new boolean[size(version)][size(version)];

        drawFunctionPatterns(matrix, function, version);
        drawCodewords(matrix, function, codewords);
        applyMask(matrix, function, mask);
        drawFormatBits(matrix, function, mask);
        return matrix;
    }

    static int size(int version) {
        return 17 + 4 * version;
    }

    private static int dataCodewords(int version) {
        int[] spec = LEVEL_M[version - 1];
        return spec[1] * spec[2];
    }

    // ------------------------------------------------------------- 数据码字

    private static byte[] buildCodewords(byte[] payload, int version) {
        int[] spec = LEVEL_M[version - 1];
        int ecPerBlock = spec[0];
        int blocks = spec[1];
        int dataPerBlock = spec[2];
        int capacityBits = dataPerBlock * blocks * 8;

        BitBuffer bits = new BitBuffer();
        bits.append(0b0100, 4);
        bits.append(payload.length, 8);
        for (byte value : payload) bits.append(value & 0xFF, 8);
        int terminator = Math.min(4, capacityBits - bits.length());
        bits.append(0, terminator);
        while (bits.length() % 8 != 0) bits.append(0, 1);
        int pad = 0;
        while (bits.length() < capacityBits) {
            bits.append(pad % 2 == 0 ? 0xEC : 0x11, 8);
            pad++;
        }

        byte[] data = bits.toBytes();
        byte[][] dataBlocks = new byte[blocks][dataPerBlock];
        byte[][] ecBlocks = new byte[blocks][ecPerBlock];
        int[] generator = rsGenerator(ecPerBlock);
        for (int block = 0; block < blocks; block++) {
            System.arraycopy(data, block * dataPerBlock, dataBlocks[block], 0, dataPerBlock);
            ecBlocks[block] = rsRemainder(dataBlocks[block], generator, ecPerBlock);
        }

        byte[] out = new byte[data.length + blocks * ecPerBlock];
        int cursor = 0;
        for (int index = 0; index < dataPerBlock; index++) {
            for (int block = 0; block < blocks; block++) {
                out[cursor++] = dataBlocks[block][index];
            }
        }
        for (int index = 0; index < ecPerBlock; index++) {
            for (int block = 0; block < blocks; block++) {
                out[cursor++] = ecBlocks[block][index];
            }
        }
        return out;
    }

    /** Generator polynomial for {@code degree} error-correction codewords. */
    private static int[] rsGenerator(int degree) {
        int[] result = new int[degree];
        result[degree - 1] = 1;
        int root = 1;
        for (int i = 0; i < degree; i++) {
            for (int j = 0; j < degree; j++) {
                result[j] = gfMultiply(result[j], root);
                if (j + 1 < degree) result[j] ^= result[j + 1];
            }
            root = gfMultiply(root, 0x02);
        }
        return result;
    }

    private static byte[] rsRemainder(byte[] data, int[] generator, int degree) {
        byte[] result = new byte[degree];
        for (byte value : data) {
            int factor = (value ^ result[0]) & 0xFF;
            System.arraycopy(result, 1, result, 0, degree - 1);
            result[degree - 1] = 0;
            for (int i = 0; i < degree; i++) {
                result[i] ^= (byte) gfMultiply(generator[i], factor);
            }
        }
        return result;
    }

    private static int gfMultiply(int left, int right) {
        int result = 0;
        for (int i = 7; i >= 0; i--) {
            result = (result << 1) ^ ((result >>> 7) * 0x11D);
            result ^= ((right >>> i) & 1) * left;
        }
        return result & 0xFF;
    }

    // ------------------------------------------------------------- 功能图形

    private static void drawFunctionPatterns(boolean[][] matrix, boolean[][] function, int version) {
        int size = matrix.length;
        for (int i = 0; i < size; i++) {
            setFunction(matrix, function, 6, i, i % 2 == 0);
            setFunction(matrix, function, i, 6, i % 2 == 0);
        }
        drawFinder(matrix, function, 3, 3);
        drawFinder(matrix, function, 3, size - 4);
        drawFinder(matrix, function, size - 4, 3);

        int[] centres = ALIGNMENT[version - 1];
        for (int row : centres) {
            for (int col : centres) {
                boolean overlapsFinder = (row == 6 && col == 6)
                        || (row == 6 && col == size - 7)
                        || (row == size - 7 && col == 6);
                if (!overlapsFinder) drawAlignment(matrix, function, row, col);
            }
        }
        // Reserve the format areas so data placement skips them; the real bits
        // are written after masking.
        for (int i = 0; i < 9; i++) {
            reserve(function, 8, i);
            reserve(function, i, 8);
        }
        for (int i = 0; i < 8; i++) {
            reserve(function, 8, size - 1 - i);
            reserve(function, size - 1 - i, 8);
        }
        setFunction(matrix, function, size - 8, 8, true);
    }

    private static void drawFinder(boolean[][] matrix, boolean[][] function, int row, int col) {
        for (int dr = -4; dr <= 4; dr++) {
            for (int dc = -4; dc <= 4; dc++) {
                int r = row + dr;
                int c = col + dc;
                if (r < 0 || c < 0 || r >= matrix.length || c >= matrix.length) continue;
                int distance = Math.max(Math.abs(dr), Math.abs(dc));
                setFunction(matrix, function, r, c, distance != 2 && distance != 4);
            }
        }
    }

    private static void drawAlignment(boolean[][] matrix, boolean[][] function, int row, int col) {
        for (int dr = -2; dr <= 2; dr++) {
            for (int dc = -2; dc <= 2; dc++) {
                int distance = Math.max(Math.abs(dr), Math.abs(dc));
                setFunction(matrix, function, row + dr, col + dc, distance != 1);
            }
        }
    }

    private static void setFunction(boolean[][] matrix, boolean[][] function,
                                    int row, int col, boolean dark) {
        if (row < 0 || col < 0 || row >= matrix.length || col >= matrix.length) return;
        matrix[row][col] = dark;
        function[row][col] = true;
    }

    private static void reserve(boolean[][] function, int row, int col) {
        if (row < 0 || col < 0 || row >= function.length || col >= function.length) return;
        function[row][col] = true;
    }

    // ------------------------------------------------------------- 数据排布

    private static void drawCodewords(boolean[][] matrix, boolean[][] function, byte[] codewords) {
        int size = matrix.length;
        int bitIndex = 0;
        int totalBits = codewords.length * 8;
        int col = size - 1;
        boolean upward = true;
        while (col > 0) {
            if (col == 6) col--;
            for (int i = 0; i < size; i++) {
                int row = upward ? size - 1 - i : i;
                for (int offset = 0; offset < 2; offset++) {
                    int x = col - offset;
                    if (function[row][x]) continue;
                    boolean dark = false;
                    if (bitIndex < totalBits) {
                        int value = codewords[bitIndex >>> 3] & 0xFF;
                        dark = ((value >>> (7 - (bitIndex & 7))) & 1) != 0;
                        bitIndex++;
                    }
                    matrix[row][x] = dark;
                }
            }
            upward = !upward;
            col -= 2;
        }
    }

    private static void applyMask(boolean[][] matrix, boolean[][] function, int mask) {
        int size = matrix.length;
        for (int row = 0; row < size; row++) {
            for (int col = 0; col < size; col++) {
                if (function[row][col]) continue;
                if (maskBit(mask, row, col)) matrix[row][col] = !matrix[row][col];
            }
        }
    }

    private static boolean maskBit(int mask, int row, int col) {
        switch (mask) {
            case 0: return (row + col) % 2 == 0;
            case 1: return row % 2 == 0;
            case 2: return col % 3 == 0;
            case 3: return (row + col) % 3 == 0;
            case 4: return (row / 2 + col / 3) % 2 == 0;
            case 5: return (row * col) % 2 + (row * col) % 3 == 0;
            case 6: return ((row * col) % 2 + (row * col) % 3) % 2 == 0;
            case 7: return ((row + col) % 2 + (row * col) % 3) % 2 == 0;
            default: throw new IllegalArgumentException("mask out of range");
        }
    }

    private static void drawFormatBits(boolean[][] matrix, boolean[][] function, int mask) {
        int size = matrix.length;
        // Level M is 00 in the format field.
        int data = (0b00 << 3) | mask;
        int remainder = data << 10;
        for (int i = 14; i >= 10; i--) {
            if (((remainder >>> i) & 1) != 0) remainder ^= 0x537 << (i - 10);
        }
        int bits = ((data << 10) | remainder) ^ 0x5412;

        // Two copies of the 15-bit type info. Bit 0 is the least significant:
        // the column beside the top-left finder takes bits 0-5, 7-8 and then
        // 8-14 at the bottom, and the row under the finder takes 0-7 on the
        // right edge, 8 next to the timing column, then 9-14 leftwards.
        // Transposing these still paints a valid-looking square, so the whole
        // encoder is compared against a reference implementation per module.
        for (int i = 0; i < 15; i++) {
            boolean dark = bit(bits, i);
            if (i < 6) {
                matrix[i][8] = dark;
            } else if (i < 8) {
                matrix[i + 1][8] = dark;
            } else {
                matrix[size - 15 + i][8] = dark;
            }
        }
        for (int i = 0; i < 15; i++) {
            boolean dark = bit(bits, i);
            if (i < 8) {
                matrix[8][size - 1 - i] = dark;
            } else if (i < 9) {
                matrix[8][15 - i] = dark;
            } else {
                matrix[8][14 - i] = dark;
            }
        }
        matrix[size - 8][8] = true;
        for (int i = 0; i < 6; i++) function[8][i] = true;
        for (int i = 0; i < 8; i++) function[8][size - 1 - i] = true;
    }

    private static boolean bit(int value, int index) {
        return ((value >>> index) & 1) != 0;
    }

    // ------------------------------------------------------------- 掩码评分

    /** Standard four-rule penalty; the mask with the lowest score wins. */
    private static int penalty(boolean[][] matrix) {
        int size = matrix.length;
        int score = 0;
        for (int row = 0; row < size; row++) {
            int run = 1;
            for (int col = 1; col < size; col++) {
                if (matrix[row][col] == matrix[row][col - 1]) {
                    run++;
                } else {
                    if (run >= 5) score += 3 + (run - 5);
                    run = 1;
                }
            }
            if (run >= 5) score += 3 + (run - 5);
        }
        for (int col = 0; col < size; col++) {
            int run = 1;
            for (int row = 1; row < size; row++) {
                if (matrix[row][col] == matrix[row - 1][col]) {
                    run++;
                } else {
                    if (run >= 5) score += 3 + (run - 5);
                    run = 1;
                }
            }
            if (run >= 5) score += 3 + (run - 5);
        }
        for (int row = 0; row < size - 1; row++) {
            for (int col = 0; col < size - 1; col++) {
                boolean value = matrix[row][col];
                if (value == matrix[row][col + 1] && value == matrix[row + 1][col]
                        && value == matrix[row + 1][col + 1]) {
                    score += 3;
                }
            }
        }
        int dark = 0;
        for (boolean[] line : matrix) {
            for (boolean value : line) if (value) dark++;
        }
        int total = size * size;
        score += Math.abs(dark * 20 - total * 10) / total * 10;
        return score;
    }

    /** Small MSB-first bit writer. */
    private static final class BitBuffer {
        private final java.io.ByteArrayOutputStream bytes = new java.io.ByteArrayOutputStream();
        private int current;
        private int filled;

        void append(int value, int count) {
            for (int i = count - 1; i >= 0; i--) {
                current = (current << 1) | ((value >>> i) & 1);
                filled++;
                if (filled == 8) {
                    bytes.write(current);
                    current = 0;
                    filled = 0;
                }
            }
        }

        int length() {
            return bytes.size() * 8 + filled;
        }

        byte[] toBytes() {
            if (filled > 0) throw new IllegalStateException("bit stream is not byte aligned");
            return bytes.toByteArray();
        }
    }
}

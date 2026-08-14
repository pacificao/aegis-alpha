import { FlatCompat } from "@eslint/eslintrc";
import path from "path";
import { fileURLToPath } from "url";
const compat = new FlatCompat({ baseDirectory: path.dirname(fileURLToPath(import.meta.url)) });
export default [...compat.extends("next/core-web-vitals", "next/typescript")];


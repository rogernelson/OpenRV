//
// Copyright (C) 2025 Autodesk, Inc. All Rights Reserved.
//
// SPDX-License-Identifier: Apache-2.0
//
#pragma once
#include <IPCore/PaintCommand.h>
#include <string>
#include <unordered_map>

namespace IPCore
{
    namespace Paint
    {

        /// Resolved properties for one catalogue brush entry.
        struct BrushInfo
        {
            unsigned int textureId = 0; ///< GL texture name; 0 = procedural
            PolyLine::StampBlendMode blendMode = PolyLine::BlendNormal;
            bool softShader = false; ///< use soft Gaussian shader
        };

        /// Singleton that loads the brush catalogue JSON and uploads tip textures to GL.
        ///
        /// Usage:
        ///   // On the GL thread, once per application lifetime:
        ///   BrushTextureManager::instance().load(catalogueDir);
        ///
        ///   // At stroke-creation time (any thread, after load()):
        ///   BrushInfo info = BrushTextureManager::instance().get(brushName);
        ///
        class BrushTextureManager
        {
        public:
            static BrushTextureManager& instance();

            /// Parse catalogue.json from @p dir and upload tip PNGs as GL textures.
            /// Must be called on the active GL thread. Safe to call multiple times —
            /// only the first call has any effect.
            void load(const std::string& dir);

            /// Return resolved info for @p name, or a default BrushInfo if not found.
            BrushInfo get(const std::string& name) const;

            /// Release all GL textures. Call before GL context teardown.
            void clear();

            bool isLoaded() const { return m_loaded; }

        private:
            BrushTextureManager() = default;

            ~BrushTextureManager() { clear(); }

            std::unordered_map<std::string, BrushInfo> m_brushes;
            bool m_loaded{false};
        };

    } // namespace Paint
} // namespace IPCore

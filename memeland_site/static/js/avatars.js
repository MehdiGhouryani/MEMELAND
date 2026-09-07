/**
 * MemeLand Vector Avatars Renderer (v6.3.0)
 */

(function() {
  const AvatarRenderer = {
    getAvatarSvg(roleKey) {
      const dim = 'width="100%" height="100%" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"';
      switch (roleKey) {
        case 'admin':
        case 'super_admin':
          return `
            <svg ${dim}>
              <rect width="100" height="100" fill="#18150c"/>
              <path d="M 28 32 L 36 44 L 50 26 L 64 44 L 72 32 L 70 50 L 30 50 Z" fill="#fbbf24" stroke="#d97706" stroke-width="1.5"/>
              <circle cx="50" cy="24" r="3" fill="#ef4444"/>
              <circle cx="28" cy="30" r="2.5" fill="#3b82f6"/>
              <circle cx="72" cy="30" r="2.5" fill="#3b82f6"/>
              <ellipse cx="50" cy="65" rx="34" ry="24" fill="#eab308"/>
              <circle cx="34" cy="46" r="11" fill="#facc15"/>
              <circle cx="66" cy="46" r="11" fill="#facc15"/>
              <rect x="22" y="44" width="24" height="14" rx="2" fill="#09090b"/>
              <rect x="54" y="44" width="24" height="14" rx="2" fill="#09090b"/>
              <line x1="46" y1="48" x2="54" y2="48" stroke="#09090b" stroke-width="3"/>
              <polygon points="25,46 32,46 27,56 23,56" fill="rgba(255,255,255,0.3)"/>
              <polygon points="57,46 64,46 59,56 55,56" fill="rgba(255,255,255,0.3)"/>
              <path d="M 32 68 Q 50 82 68 68" fill="none" stroke="#713f12" stroke-width="3.5" stroke-linecap="round"/>
            </svg>
          `;

        case 'vip_helper':
          return `
            <svg ${dim}>
              <rect width="100" height="100" fill="#111827"/>
              <ellipse cx="50" cy="65" rx="30" ry="25" fill="#d97706"/>
              <ellipse cx="50" cy="68" rx="18" ry="14" fill="#fef3c7"/>
              <circle cx="38" cy="60" r="3.5" fill="#111827"/>
              <circle cx="62" cy="60" r="3.5" fill="#111827"/>
              <ellipse cx="50" cy="66" rx="4.5" ry="3" fill="#111827"/>
              <path d="M 22 52 C 22 28, 78 28, 78 52 Z" fill="#ec4899"/>
              <rect x="18" y="48" width="64" height="8" rx="3" fill="#f472b6"/>
              <line x1="30" y1="36" x2="30" y2="48" stroke="#db2777" stroke-width="2"/>
              <line x1="50" y1="32" x2="50" y2="48" stroke="#db2777" stroke-width="2"/>
              <line x1="70" y1="36" x2="70" y2="48" stroke="#db2777" stroke-width="2"/>
              <circle cx="50" cy="27" r="5" fill="#fbcfe8"/>
            </svg>
          `;

        case 'og':
          return `
            <svg ${dim}>
              <rect width="100" height="100" fill="#1c1917"/>
              <path d="M 18 85 L 30 55 L 70 55 L 82 85 Z" fill="#dc2626"/>
              <ellipse cx="50" cy="55" rx="18" ry="5" fill="#fef08a"/>
              <circle cx="50" cy="48" r="26" fill="#eab308"/>
              <ellipse cx="50" cy="52" rx="15" ry="12" fill="#fef9c3"/>
              <polygon points="26,34 36,18 42,32" fill="#ca8a04"/>
              <polygon points="74,34 64,18 58,32" fill="#ca8a04"/>
              <ellipse cx="40" cy="45" rx="3.5" ry="4" fill="#1c1917"/>
              <ellipse cx="60" cy="45" rx="3.5" ry="4" fill="#1c1917"/>
              <circle cx="39" cy="43.5" r="1.2" fill="#ffffff"/>
              <circle cx="59" cy="43.5" r="1.2" fill="#ffffff"/>
              <ellipse cx="50" cy="50" rx="4" ry="3" fill="#1c1917"/>
              <path d="M 46 54 Q 50 57 54 54" fill="none" stroke="#1c1917" stroke-width="1.8"/>
            </svg>
          `;

        case 'alpha':
          return `
            <svg ${dim}>
              <rect width="100" height="100" fill="#064e3b"/>
              <circle cx="50" cy="52" r="34" fill="#f3f4f6" stroke="#9ca3af" stroke-width="2"/>
              <ellipse cx="50" cy="52" rx="26" ry="20" fill="#09090b"/>
              <line x1="38" y1="42" x2="38" y2="60" stroke="#10b981" stroke-width="1.5"/>
              <rect x="35.5" y="46" width="5" height="9" fill="#10b981"/>
              <line x1="48" y1="38" x2="48" y2="58" stroke="#10b981" stroke-width="1.5"/>
              <rect x="45.5" y="41" width="5" height="11" fill="#10b981"/>
              <line x1="58" y1="36" x2="58" y2="54" stroke="#10b981" stroke-width="1.5"/>
              <rect x="55.5" y="38" width="5" height="10" fill="#10b981"/>
              <path d="M 32 44 Q 50 36 68 44" fill="none" stroke="rgba(255,255,255,0.4)" stroke-width="2.5" stroke-linecap="round"/>
            </svg>
          `;

        case 'guardian':
          return `
            <svg ${dim}>
              <rect width="100" height="100" fill="#0c4a6e"/>
              <path d="M 45 16 Q 52 14 62 26 L 48 30 Z" fill="#0284c7"/>
              <ellipse cx="50" cy="58" rx="30" ry="26" fill="#0369a1"/>
              <ellipse cx="50" cy="65" rx="22" ry="16" fill="#e0f2fe"/>
              <circle cx="36" cy="52" r="3.5" fill="#082f49"/>
              <circle cx="64" cy="52" r="3.5" fill="#082f49"/>
              <path d="M 34 68 Q 50 78 66 68 Z" fill="#082f49"/>
              <polygon points="40,68 43,72 46,68" fill="#ffffff"/>
              <polygon points="48,69 51,74 54,69" fill="#fbbf24"/>
              <polygon points="56,68 59,72 62,68" fill="#ffffff"/>
            </svg>
          `;

        case 'explorer':
          return `
            <svg ${dim}>
              <rect width="100" height="100" fill="#14532d"/>
              <ellipse cx="50" cy="64" rx="32" ry="22" fill="#4ade80"/>
              <circle cx="34" cy="46" r="10" fill="#4ade80"/>
              <circle cx="66" cy="46" r="10" fill="#4ade80"/>
              <circle cx="34" cy="46" r="7" fill="#ffffff"/>
              <circle cx="66" cy="46" r="7" fill="#ffffff"/>
              <circle cx="35" cy="46" r="3.5" fill="#052e16"/>
              <circle cx="67" cy="46" r="3.5" fill="#052e16"/>
              <ellipse cx="50" cy="38" rx="34" ry="8" fill="#a16207"/>
              <path d="M 28 38 C 28 20, 72 20, 72 38 Z" fill="#ca8a04"/>
              <path d="M 34 68 Q 50 80 66 68" fill="none" stroke="#14532d" stroke-width="3" stroke-linecap="round"/>
            </svg>
          `;

        case 'rookie':
        default:
          return `
            <svg ${dim}>
              <rect width="100" height="100" fill="#27272a"/>
              <circle cx="50" cy="50" r="24" fill="#facc15"/>
              <circle cx="42" cy="46" r="3.5" fill="#18181b"/>
              <circle cx="58" cy="46" r="3.5" fill="#18181b"/>
              <circle cx="43" cy="45" r="1.2" fill="#ffffff"/>
              <circle cx="59" cy="45" r="1.2" fill="#ffffff"/>
              <polygon points="47,51 53,51 50,56" fill="#ea580c"/>
              <path d="M 24 64 Q 50 56 76 64 L 76 76 C 76 88, 24 88, 24 76 Z" fill="#f4f4f5"/>
              <polygon points="30,64 36,58 42,64 48,57 54,64 62,58 70,64" fill="#e4e4e7"/>
            </svg>
          `;
      }
    },

    getRoleMiniBadge(roleKey) {
      const badges = {
        admin: '👑',
        super_admin: '👑',
        vip_helper: '💎',
        og: '🔱',
        alpha: '🚀',
        guardian: '🦈',
        explorer: '🐸',
        rookie: '🐣'
      };
      return badges[roleKey] || '🐣';
    }
  };

  window.AvatarRenderer = AvatarRenderer;
  if (window.sendRemoteLog) window.sendRemoteLog('AVATAR: Renderer Ready');
})();
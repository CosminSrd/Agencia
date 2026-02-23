/**
 * Cookie Consent Banner - Viatges Carcaixent
 * Complies with GDPR & ePrivacy Directive
 */

(function () {
    'use strict';

    const COOKIE_CONSENT_KEY = 'cookie_consent_status';
    const CONSENT_VERSION = '1.0'; // Increment to force re-consent if policies change

    function initCookieConsent() {
        // 1. Check if user already consented
        const savedConsent = localStorage.getItem(COOKIE_CONSENT_KEY);
        if (savedConsent) {
            // Optional: Check version if needed
            return;
        }

        // 2. Inject Styles
        const style = document.createElement('style');
        style.id = 'cookie-consent-style';
        style.textContent = `
            .cookie-banner {
                position: fixed;
                bottom: 20px;
                left: 50%;
                transform: translateX(-50%);
                width: 90%;
                max-width: 1000px;
                background: #ffffff;
                color: #1e293b;
                padding: 20px 30px;
                border-radius: 16px;
                box-shadow: 0 10px 40px rgba(0,0,0,0.15);
                z-index: 99999;
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 20px;
                border: 1px solid #e2e8f0;
                font-family: 'Inter', sans-serif;
                animation: slideUp 0.5s ease-out forwards;
            }

            @media (max-width: 768px) {
                .cookie-banner {
                    flex-direction: column;
                    text-align: center;
                    bottom: 0;
                    width: 100%;
                    border-radius: 16px 16px 0 0;
                    padding: 25px 20px;
                }
            }

            .cookie-content {
                flex: 1;
            }

            .cookie-title {
                font-weight: 700;
                font-size: 1rem;
                margin-bottom: 5px;
                display: flex;
                align-items: center;
                gap: 8px;
            }

            .cookie-text {
                font-size: 0.9rem;
                color: #64748b;
                line-height: 1.5;
            }

            .cookie-text a {
                color: #6366f1;
                text-decoration: none;
                font-weight: 500;
            }

            .cookie-text a:hover {
                text-decoration: underline;
            }

            .cookie-buttons {
                display: flex;
                gap: 10px;
            }

            .btn-cookie {
                padding: 10px 20px;
                border-radius: 8px;
                font-size: 0.9rem;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.2s;
                border: none;
            }

            .btn-accept {
                background: #0f172a;
                color: white;
            }

            .btn-accept:hover {
                background: #1e293b;
                transform: translateY(-1px);
            }

            .btn-reject {
                background: #f1f5f9;
                color: #475569;
            }

            .btn-reject:hover {
                background: #e2e8f0;
            }

            @keyframes slideUp {
                from { opacity: 0; transform: translate(-50%, 50px); }
                to { opacity: 1; transform: translate(-50%, 0); }
            }
        `;
        document.head.appendChild(style);

        // 3. Inject HTML
        const banner = document.createElement('div');
        banner.className = 'cookie-banner';
        banner.innerHTML = `
            <div class="cookie-content">
                <div class="cookie-title">🍪 Privacidad y Cookies</div>
                <div class="cookie-text">
                    Utilizamos cookies para garantizar que obtengas la mejor experiencia en nuestro sitio web, personalizar contenido y analizar nuestro tráfico. 
                    Consulta nuestra <a href="/legal" target="_blank">Política de Privacidad</a>.
                </div>
            </div>
            <div class="cookie-buttons">
                <!-- <button class="btn-cookie btn-reject" id="btn-reject-cookies">Solo necesarias</button> -->
                <button class="btn-cookie btn-accept" id="btn-accept-cookies">Aceptar todo</button>
            </div>
        `;
        document.body.appendChild(banner);

        // 4. Event Listeners
        document.getElementById('btn-accept-cookies').addEventListener('click', () => {
            handleConsent(true);
        });

        /* 
        document.getElementById('btn-reject-cookies').addEventListener('click', () => {
            handleConsent(false);
        });
        */

        function handleConsent(accepted) {
            const consentData = {
                status: accepted ? 'accepted' : 'rejected',
                timestamp: new Date().toISOString(),
                version: CONSENT_VERSION
            };
            localStorage.setItem(COOKIE_CONSENT_KEY, JSON.stringify(consentData));

            // Animate out
            banner.style.opacity = '0';
            banner.style.transform = 'translate(-50%, 20px)';
            setTimeout(() => {
                banner.remove();
            }, 500);

            // Here we could trigger loading of analytics scripts if accepted
            if (accepted) {
                // loadAnalytics();
            }
        }
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initCookieConsent);
    } else {
        initCookieConsent();
    }

})();

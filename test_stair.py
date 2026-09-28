# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — Test BEK-STAIR
# ------------------------------------------------------------------------------
# 🏛️ BREVET : BEK-STAIR-v1.0
# 📄 Doc : docs/brevets/BREVET_STAIR.md
# 🎯 Rôle : Test de l'anti-hallucination via ToC
# ------------------------------------------------------------------------------
# Auteur : BEK Project
# Version : 1.0
# Date : 2026-09-23
# ==============================================================================

"""
Test BEK-STAIR — Vérification de l'anti-hallucination.

Simule :
    1. 3 pages scrapées (CoinMarketCap, Crypto.com, Wikipedia)
    2. Une réponse LLM correcte → valid=True
    3. Une réponse LLM avec URL inventée → valid=False
    4. Une réponse LLM avec source inventée → valid=False
"""

import sys
from pathlib import Path

# Ajouter la racine au path
sys.path.insert(0, str(Path(__file__).parent))

from bek_core.stair import BekStairToC


def main():
    print("\n" + "=" * 70)
    print("🧪 TEST BEK-STAIR — Anti-Hallucination ToC")
    print("=" * 70)

    # ─── 1. Pages simulées ───
    pages = [
        {
            "title": "Bitcoin price today | CoinMarketCap",
            "url": "https://coinmarketcap.com/currencies/bitcoin/",
            "content": (
                "Bitcoin is a decentralized cryptocurrency originally described in a 2008 whitepaper. "
                "Bitcoin price today is $68,500 with a 24h trading volume of $25 billion. "
                "The current market cap is $1.35 trillion."
            ),
        },
        {
            "title": "Bitcoin Cours aujourd'hui | Crypto.com",
            "url": "https://crypto.com/fr/price/bitcoin",
            "content": (
                "Bitcoin (BTC) est la première cryptomonnaie au monde. "
                "Le cours actuel du Bitcoin est de 68 500 dollars. "
                "Il repose sur la technologie des registres distribués."
            ),
        },
        {
            "title": "Bitcoin - Wikipedia",
            "url": "https://fr.wikipedia.org/wiki/Bitcoin",
            "content": (
                "Le bitcoin est une cryptomonnaie pair-à-pair. "
                "Il a été créé en 2008 par Satoshi Nakamoto. "
                "Le premier bloc a été miné le 3 janvier 2009."
            ),
        },
    ]

    query = "Quel est le prix du Bitcoin aujourd'hui ?"

    # ─── 2. Construire le ToC ───
    print("\n📝 ÉTAPE 1 — Construction du ToC")
    print("-" * 70)
    toc = BekStairToC()
    toc_context = toc.build(pages, query)
    print(toc_context[:1500])
    print("... [ToC tronqué pour affichage]")

    # ─── 3. Test 1 : Réponse correcte ───
    print("\n" + "=" * 70)
    print("✅ TEST 1 — Réponse correcte (sources valides)")
    print("=" * 70)

    correct_response = (
        "Selon [S1] CoinMarketCap, le Bitcoin est actuellement à 68 500 dollars. "
        "Le site [S2] Crypto.com confirme ce cours à 68 500 dollars. "
        "D'après [S3] Wikipedia, le Bitcoin a été créé en 2008 par Satoshi Nakamoto. "
        "Source : https://coinmarketcap.com/currencies/bitcoin/"
    )

    print(f"\n📄 Réponse LLM :\n{correct_response}\n")

    result1 = toc.validate(correct_response, toc_context, pages)
    print(f"🎯 Résultat : valid={result1['valid']} | score={result1['score']}")

    if result1['hallucinations']:
        print(f"❌ Hallucinations : {result1['hallucinations']}")
    else:
        print("✅ Aucune hallucination détectée")

    assert result1['valid'] is True, "TEST 1 ÉCHOUÉ"
    print("✅ TEST 1 PASSÉ")

    # ─── 4. Test 2 : URL inventée ───
    print("\n" + "=" * 70)
    print("❌ TEST 2 — URL inventée (hallucination)")
    print("=" * 70)

    invented_url_response = (
        "Selon Reuters, le Bitcoin a chuté de 15% aujourd'hui. "
        "Source : https://reuters.com/bitcoin-news-2026-09-23.html "
        "Voir aussi https://fake-news-crypto.com/article-12345"
    )

    print(f"\n📄 Réponse LLM :\n{invented_url_response}\n")

    result2 = toc.validate(invented_url_response, toc_context, pages)
    print(f"🎯 Résultat : valid={result2['valid']} | score={result2['score']}")

    if result2['hallucinations']:
        print(f"❌ Hallucinations détectées : {len(result2['hallucinations'])}")
        for h in result2['hallucinations']:
            print(f"   → {h['type']}: {h['detail']}")

    assert result2['valid'] is False, "TEST 2 ÉCHOUÉ — devrait rejeter"
    print("✅ TEST 2 PASSÉ (hallucination détectée)")

    # ─── 5. Test 3 : Source inventée ───
    print("\n" + "=" * 70)
    print("❌ TEST 3 — Source inventée (hallucination)")
    print("=" * 70)

    invented_source_response = (
        "Selon Bloomberg, le Bitcoin a atteint un nouveau record. "
        "D'après Le Monde, les investisseurs sont optimistes. "
        "L'analyse de Forbes indique une tendance haussière."
    )

    print(f"\n📄 Réponse LLM :\n{invented_source_response}\n")

    result3 = toc.validate(invented_source_response, toc_context, pages)
    print(f"🎯 Résultat : valid={result3['valid']} | score={result3['score']}")

    if result3['hallucinations']:
        print(f"❌ Hallucinations détectées : {len(result3['hallucinations'])}")
        for h in result3['hallucinations']:
            print(f"   → {h['type']}: {h['detail']}")

    assert result3['valid'] is False, "TEST 3 ÉCHOUÉ — devrait rejeter"
    print("✅ TEST 3 PASSÉ (sources inventées détectées)")

    # ─── 6. Récapitulatif ───
    print("\n" + "=" * 70)
    print("🎉 TOUS LES TESTS BEK-STAIR PASSENT")
    print("=" * 70)
    print("\n📊 Récapitulatif :")
    print(f"  Test 1 (réponse correcte)    : valid={result1['valid']} | score={result1['score']}")
    print(f"  Test 2 (URL inventée)        : valid={result2['valid']} | score={result2['score']}")
    print(f"  Test 3 (sources inventées)   : valid={result3['valid']} | score={result3['score']}")
    print("\n✅ BEK-STAIR est opérationnel.\n")


if __name__ == "__main__":
    main()
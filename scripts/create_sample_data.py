#!/usr/bin/env python3
"""
Create sample botanical data for testing the repertory.
Run this to populate the database with realistic sample data.
"""

import sys
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.database import BotanicalDatabase
from src.models import Botanical, Indication, BotanicalIndicationLink, Contraindication


def create_sample_botanicals():
    """Create sample botanical records."""
    return [
        Botanical(
            latin_binomial="Matricaria recutita",
            common_names=["Chamomile", "German Chamomile", "Wild Chamomile"],
            family="Asteraceae",
            parts_used=["flowers", "essential oil"],
            energetics={"temperature": "cool", "moisture": "dry"},
            traditional_systems=["Western herbalism", "Ayurveda", "Traditional Chinese Medicine"]
        ),
        Botanical(
            latin_binomial="Hypericum perforatum",
            common_names=["St. John's Wort", "Tipton's Weed", "Goatweed"],
            family="Hypericaceae",
            parts_used=["flowering tops", "leaves"],
            energetics={"temperature": "warm", "moisture": "dry"},
            traditional_systems=["Western herbalism", "European traditional"]
        ),
        Botanical(
            latin_binomial="Valeriana officinalis",
            common_names=["Valerian", "Garden Heliotrope", "All-Heal"],
            family="Caprifoliaceae",
            parts_used=["root", "rhizome"],
            energetics={"temperature": "warm", "moisture": "moist"},
            traditional_systems=["Western herbalism", "European traditional", "Ayurveda"]
        ),
        Botanical(
            latin_binomial="Ginkgo biloba",
            common_names=["Ginkgo", "Maidenhair Tree"],
            family="Ginkgoaceae",
            parts_used=["leaves"],
            energetics={"temperature": "neutral", "moisture": "dry"},
            traditional_systems=["Traditional Chinese Medicine", "Western herbalism"]
        ),
        Botanical(
            latin_binomial="Echinacea purpurea",
            common_names=["Purple Coneflower", "Echinacea"],
            family="Asteraceae",
            parts_used=["root", "aerial parts"],
            energetics={"temperature": "cool", "moisture": "dry"},
            traditional_systems=["Native American", "Western herbalism"]
        ),
        Botanical(
            latin_binomial="Zingiber officinale",
            common_names=["Ginger", "Garden Ginger"],
            family="Zingiberaceae",
            parts_used=["rhizome"],
            energetics={"temperature": "hot", "moisture": "dry"},
            traditional_systems=["Ayurveda", "Traditional Chinese Medicine", "Western herbalism"]
        ),
        Botanical(
            latin_binomial="Crataegus laevigata",
            common_names=["Hawthorn", "Maybush", "Whitethorn"],
            family="Rosaceae",
            parts_used=["berry", "leaf", "flower"],
            energetics={"temperature": "warm", "moisture": "moist"},
            traditional_systems=["Western herbalism", "European traditional"]
        ),
        Botanical(
            latin_binomial="Silybum marianum",
            common_names=["Milk Thistle", "St. Mary's Thistle"],
            family="Asteraceae",
            parts_used=["seed"],
            energetics={"temperature": "cool", "moisture": "dry"},
            traditional_systems=["Western herbalism", "European traditional"]
        ),
        Botanical(
            latin_binomial="Tanacetum parthenium",
            common_names=["Feverfew", "Featherfew"],
            family="Asteraceae",
            parts_used=["leaf", "flowering tops"],
            energetics={"temperature": "cool", "moisture": "dry"},
            traditional_systems=["Western herbalism", "European traditional"]
        ),
        Botanical(
            latin_binomial="Vaccinium myrtillus",
            common_names=["Bilberry", "European Blueberry", "Whortleberry"],
            family="Ericaceae",
            parts_used=["fruit", "leaf"],
            energetics={"temperature": "cool", "moisture": "astringent"},
            traditional_systems=["Western herbalism", "European traditional"]
        ),
        Botanical(
            latin_binomial="Allium sativum",
            common_names=["Garlic", "Clove Garlic"],
            family="Amaryllidaceae",
            parts_used=["bulb"],
            energetics={"temperature": "hot", "moisture": "dry"},
            traditional_systems=["Ayurveda", "Traditional Chinese Medicine", "Western herbalism"]
        ),
        Botanical(
            latin_binomial="Panax ginseng",
            common_names=["Asian Ginseng", "Korean Ginseng", "Ren Shen"],
            family="Araliaceae",
            parts_used=["root"],
            energetics={"temperature": "warm", "moisture": "moist"},
            traditional_systems=["Traditional Chinese Medicine", "Korean traditional"]
        ),
    ]


def create_sample_indications():
    """Create sample indication records."""
    return [
        # Sleep
        Indication(indication_text="Insomnia", normalized_text="insomnia", category="sleep"),
        Indication(indication_text="Difficulty falling asleep", normalized_text="difficulty falling asleep", category="sleep"),
        Indication(indication_text="Sleep maintenance insomnia", normalized_text="sleep maintenance insomnia", category="sleep"),
        
        # Mental/Emotional
        Indication(indication_text="Anxiety", normalized_text="anxiety", category="mental"),
        Indication(indication_text="Generalized anxiety disorder", normalized_text="generalized anxiety disorder", category="mental"),
        Indication(indication_text="Mild to moderate depression", normalized_text="mild to moderate depression", category="mental"),
        Indication(indication_text="Nervous tension", normalized_text="nervous tension", category="mental"),
        Indication(indication_text="Stress", normalized_text="stress", category="mental"),
        Indication(indication_text="Cognitive decline", normalized_text="cognitive decline", category="mental"),
        Indication(indication_text="Memory impairment", normalized_text="memory impairment", category="mental"),
        
        # Cardiovascular
        Indication(indication_text="Mild heart failure", normalized_text="mild heart failure", category="cardiovascular"),
        Indication(indication_text="Hypertension", normalized_text="hypertension", category="cardiovascular"),
        Indication(indication_text="Hyperlipidemia", normalized_text="hyperlipidemia", category="cardiovascular"),
        Indication(indication_text="Atherosclerosis", normalized_text="atherosclerosis", category="cardiovascular"),
        Indication(indication_text="Peripheral vascular disease", normalized_text="peripheral vascular disease", category="cardiovascular"),
        Indication(indication_text="Intermittent claudication", normalized_text="intermittent claudication", category="cardiovascular"),
        
        # Digestive
        Indication(indication_text="Nausea", normalized_text="nausea", category="digestive"),
        Indication(indication_text="Morning sickness", normalized_text="morning sickness", category="digestive"),
        Indication(indication_text="Motion sickness", normalized_text="motion sickness", category="digestive"),
        Indication(indication_text="Dyspepsia", normalized_text="dyspepsia", category="digestive"),
        Indication(indication_text="Indigestion", normalized_text="indigestion", category="digestive"),
        Indication(indication_text="Diarrhea", normalized_text="diarrhea", category="digestive"),
        Indication(indication_text="Irritable bowel syndrome", normalized_text="irritable bowel syndrome", category="digestive"),
        
        # Pain/Neurological
        Indication(indication_text="Migraine prevention", normalized_text="migraine prevention", category="pain"),
        Indication(indication_text="Nerve pain", normalized_text="nerve pain", category="pain"),
        Indication(indication_text="Neuralgia", normalized_text="neuralgia", category="pain"),
        Indication(indication_text="Muscle spasms", normalized_text="muscle spasms", category="pain"),
        Indication(indication_text="Tinnitus", normalized_text="tinnitus", category="pain"),
        
        # Immune/Infectious
        Indication(indication_text="Upper respiratory infection", normalized_text="upper respiratory infection", category="immune"),
        Indication(indication_text="Common cold", normalized_text="common cold", category="immune"),
        Indication(indication_text="Immune support", normalized_text="immune support", category="immune"),
        Indication(indication_text="Influenza", normalized_text="influenza", category="immune"),
        
        # Liver/Detox
        Indication(indication_text="Liver disease", normalized_text="liver disease", category="liver"),
        Indication(indication_text="Hepatotoxicity", normalized_text="hepatotoxicity", category="liver"),
        Indication(indication_text="Alcoholic liver disease", normalized_text="alcoholic liver disease", category="liver"),
        
        # Eye
        Indication(indication_text="Diabetic retinopathy", normalized_text="diabetic retinopathy", category="eye"),
        Indication(indication_text="Night vision impairment", normalized_text="night vision impairment", category="eye"),
        
        # Skin/External
        Indication(indication_text="Wound healing", normalized_text="wound healing", category="skin"),
        Indication(indication_text="Skin inflammation", normalized_text="skin inflammation", category="skin"),
        Indication(indication_text="Eczema", normalized_text="eczema", category="skin"),
        
        # Women's health
        Indication(indication_text="Low milk supply", normalized_text="low milk supply", category="womens_health"),
        
        # Men's health
        Indication(indication_text="Erectile dysfunction", normalized_text="erectile dysfunction", category="mens_health"),
        
        # Other
        Indication(indication_text="Fatigue", normalized_text="fatigue", category="general"),
        Indication(indication_text="Varicose veins", normalized_text="varicose veins", category="circulatory"),
    ]


def create_sample_links():
    """Create sample botanical-indication links with evidence levels."""
    return [
        # Chamomile - strong evidence for anxiety/sleep
        ("Matricaria recutita", "insomnia", "clinical_trial", 2.5),
        ("Matricaria recutita", "difficulty falling asleep", "clinical_trial", 2.0),
        ("Matricaria recutita", "anxiety", "clinical_trial", 2.5),
        ("Matricaria recutita", "generalized anxiety disorder", "clinical_trial", 2.0),
        ("Matricaria recutita", "dyspepsia", "clinical_observation", 1.5),
        ("Matricaria recutita", "skin inflammation", "traditional", 1.0),
        ("Matricaria recutita", "wound healing", "traditional", 1.0),
        ("Matricaria recutita", "irritable bowel syndrome", "clinical_observation", 1.5),
        
        # St. John's Wort - depression/anxiety
        ("Hypericum perforatum", "mild to moderate depression", "systematic_review", 3.0),
        ("Hypericum perforatum", "anxiety", "clinical_observation", 1.5),
        ("Hypericum perforatum", "nervous tension", "traditional", 1.0),
        ("Hypericum perforatum", "nerve pain", "clinical_observation", 1.5),
        ("Hypericum perforatum", "wound healing", "traditional", 1.0),
        
        # Valerian - sleep
        ("Valeriana officinalis", "insomnia", "clinical_trial", 2.0),
        ("Valeriana officinalis", "sleep maintenance insomnia", "clinical_trial", 2.0),
        ("Valeriana officinalis", "anxiety", "clinical_observation", 1.5),
        ("Valeriana officinalis", "nervous tension", "traditional", 1.0),
        ("Valeriana officinalis", "muscle spasms", "traditional", 1.0),
        
        # Ginkgo - cognitive/cardiovascular
        ("Ginkgo biloba", "cognitive decline", "clinical_trial", 2.0),
        ("Ginkgo biloba", "memory impairment", "clinical_trial", 1.5),
        ("Ginkgo biloba", "intermittent claudication", "clinical_trial", 2.0),
        ("Ginkgo biloba", "peripheral vascular disease", "clinical_trial", 2.0),
        ("Ginkgo biloba", "tinnitus", "clinical_observation", 1.0),
        
        # Echinacea - immune
        ("Echinacea purpurea", "common cold", "clinical_trial", 1.5),
        ("Echinacea purpurea", "upper respiratory infection", "clinical_trial", 1.5),
        ("Echinacea purpurea", "immune support", "clinical_observation", 1.5),
        ("Echinacea purpurea", "influenza", "clinical_observation", 1.0),
        ("Echinacea purpurea", "wound healing", "traditional", 1.0),
        
        # Ginger - nausea/digestive
        ("Zingiber officinale", "nausea", "systematic_review", 3.0),
        ("Zingiber officinale", "morning sickness", "clinical_trial", 2.5),
        ("Zingiber officinale", "motion sickness", "clinical_trial", 2.0),
        ("Zingiber officinale", "dyspepsia", "clinical_trial", 2.0),
        ("Zingiber officinale", "indigestion", "clinical_observation", 1.5),
        ("Zingiber officinale", "inflammation", "clinical_trial", 2.0),
        ("Zingiber officinale", "muscle spasms", "clinical_observation", 1.0),
        
        # Hawthorn - cardiovascular
        ("Crataegus laevigata", "mild heart failure", "systematic_review", 3.0),
        ("Crataegus laevigata", "hypertension", "clinical_trial", 2.0),
        ("Crataegus laevigata", "anxiety", "traditional", 1.0),
        ("Crataegus laevigata", "atherosclerosis", "clinical_observation", 1.0),
        
        # Milk Thistle - liver
        ("Silybum marianum", "liver disease", "clinical_trial", 2.0),
        ("Silybum marianum", "hepatotoxicity", "clinical_trial", 2.5),
        ("Silybum marianum", "low milk supply", "traditional", 1.0),
        
        # Feverfew - migraine
        ("Tanacetum parthenium", "migraine prevention", "clinical_trial", 2.0),
        ("Tanacetum parthenium", "arthritis", "clinical_observation", 1.0),
        
        # Bilberry - eye/circulatory
        ("Vaccinium myrtillus", "diabetic retinopathy", "clinical_trial", 2.0),
        ("Vaccinium myrtillus", "night vision impairment", "clinical_observation", 1.0),
        ("Vaccinium myrtillus", "diarrhea", "traditional", 1.0),
        ("Vaccinium myrtillus", "varicose veins", "clinical_observation", 1.0),
        
        # Garlic - cardiovascular
        ("Allium sativum", "hyperlipidemia", "systematic_review", 3.0),
        ("Allium sativum", "hypertension", "systematic_review", 3.0),
        ("Allium sativum", "atherosclerosis", "clinical_observation", 1.5),
        ("Allium sativum", "infections", "traditional", 1.0),
        ("Allium sativum", "immune support", "traditional", 1.0),
        
        # Ginseng - adaptogen
        ("Panax ginseng", "fatigue", "clinical_trial", 1.5),
        ("Panax ginseng", "stress", "clinical_observation", 1.0),
        ("Panax ginseng", "cognitive decline", "clinical_trial", 1.5),
        ("Panax ginseng", "immune support", "clinical_trial", 1.5),
        ("Panax ginseng", "erectile dysfunction", "clinical_trial", 1.5),
    ]


def create_sample_contraindications():
    """Create sample safety/contraindication records."""
    return [
        # St. John's Wort - major interactions
        ("Hypericum perforatum", "Photosensitivity", "moderate", "May cause photosensitivity; use sunscreen"),
        ("Hypericum perforatum", "MAO inhibitors", "absolute", "Contraindicated with MAOIs - risk of serotonin syndrome"),
        ("Hypericum perforatum", "SSRIs/SNRIs", "absolute", "Risk of serotonin syndrome"),
        ("Hypericum perforatum", "Oral contraceptives", "severe", "May reduce efficacy"),
        ("Hypericum perforatum", "Warfarin", "severe", "May reduce anticoagulant effect"),
        ("Hypericum perforatum", "Cyclosporine", "severe", "May reduce drug levels"),
        ("Hypericum perforatum", "HIV protease inhibitors", "severe", "May reduce drug levels"),
        ("Hypericum perforatum", "Digoxin", "moderate", "May reduce drug levels"),
        
        # Ginkgo - bleeding risk
        ("Ginkgo biloba", "Bleeding disorders", "moderate", "May increase bleeding risk"),
        ("Ginkgo biloba", "Anticoagulants", "severe", "Increased bleeding risk with warfarin"),
        ("Ginkgo biloba", "Surgery", "moderate", "Discontinue 2 weeks before surgery"),
        ("Ginkgo biloba", "Seizure disorders", "moderate", "Raw seeds may cause seizures"),
        
        # Feverfew - pregnancy/ surgery
        ("Tanacetum parthenium", "Pregnancy", "absolute", "Contraindicated in pregnancy - uterine stimulant"),
        ("Tanacetum parthenium", "Surgery", "moderate", "Discontinue before surgery - bleeding risk"),
        ("Tanacetum parthenium", "Asteraceae allergy", "moderate", "Caution with ragweed allergy"),
        
        # Valerian - sedation
        ("Valeriana officinalis", "CNS depressants", "moderate", "Additive sedation with alcohol, benzodiazepines"),
        ("Valeriana officinalis", "Surgery", "moderate", "Discontinue before surgery"),
        
        # Garlic - bleeding
        ("Allium sativum", "Bleeding disorders", "mild", "May increase bleeding at high doses"),
        ("Allium sativum", "Anticoagulants", "moderate", "May potentiate warfarin effect"),
        ("Allium sativum", "Surgery", "moderate", "Discontinue 2 weeks before surgery at high doses"),
        
        # Ginger - bleeding/pregnancy
        ("Zingiber officinale", "Bleeding disorders", "mild", "High doses may increase bleeding risk"),
        ("Zingiber officinale", "Gallstones", "moderate", "May stimulate bile production"),
        
        # Ginseng - various
        ("Panax ginseng", "Hypertension", "mild", "May elevate blood pressure in some"),
        ("Panax ginseng", "Insomnia", "mild", "May cause insomnia if taken late in day"),
        ("Panax ginseng", "Anticoagulants", "moderate", "May affect warfarin"),
        ("Panax ginseng", "Diabetes", "moderate", "May affect blood glucose"),
        
        # Hawthorn - heart conditions
        ("Crataegus laevigata", "Heart medications", "moderate", "May potentiate cardiac glycosides, antihypertensives"),
        ("Crataegus laevigata", "Severe heart conditions", "moderate", "Use only under medical supervision"),
        
        # Echinacea - autoimmune
        ("Echinacea purpurea", "Autoimmune disorders", "moderate", "Theoretical concern - may stimulate immune system"),
        ("Echinacea purpurea", "Asteraceae allergy", "moderate", "Caution with ragweed allergy"),
        ("Echinacea purpurea", "HIV/AIDS", "moderate", "Consult provider - theoretical immunostimulant concern"),
        
        # Chamomile - allergies
        ("Matricaria recutita", "Asteraceae allergy", "moderate", "Caution with ragweed, chrysanthemum allergy"),
        
        # Milk thistle - hormones
        ("Silybum marianum", "Hormone-sensitive conditions", "mild", "Weak estrogenic activity - use caution"),
    ]


def main():
    """Main function to create sample data."""
    print("=" * 60)
    print("CREATING SAMPLE BOTANICAL DATA")
    print("=" * 60)
    print()
    
    # Initialize database
    db = BotanicalDatabase()
    db.initialize_schema()
    
    # Get existing counts
    initial_stats = db.get_stats()
    print(f"Initial database state:")
    for table, count in initial_stats.items():
        print(f"  {table}: {count}")
    print()
    
    # Create botanicals
    print("🌱 Creating botanicals...")
    botanicals = create_sample_botanicals()
    bot_id_map = {}
    for bot in botanicals:
        bot_id = db.insert_botanical(bot)
        bot_id_map[bot.latin_binomial] = bot_id
        print(f"  ✓ {bot.short_name}")
    print(f"  Created {len(botanicals)} botanicals\n")
    
    # Create indications
    print("🔍 Creating indications...")
    indications = create_sample_indications()
    ind_id_map = {}
    for ind in indications:
        ind_id = db.insert_indication(ind)
        ind_id_map[ind.normalized_text] = ind_id
    print(f"  Created {len(indications)} indications\n")
    
    # Create links
    print("🔗 Creating botanical-indication links...")
    links_data = create_sample_links()
    links_created = 0
    for bot_name, ind_text, evidence, weight in links_data:
        bot_id = bot_id_map.get(bot_name)
        ind_id = ind_id_map.get(ind_text)
        if bot_id and ind_id:
            link = BotanicalIndicationLink(
                botanical_id=bot_id,
                indication_id=ind_id,
                evidence_level=evidence,
                weight=weight
            )
            db.insert_edge(link)
            links_created += 1
    print(f"  Created {links_created} links\n")
    
    # Create contraindications
    print("⚠️  Creating safety data...")
    contras = create_sample_contraindications()
    contras_created = 0
    for bot_name, contra_text, severity, notes in contras:
        bot_id = bot_id_map.get(bot_name)
        if bot_id:
            contra = Contraindication(
                botanical_id=bot_id,
                contraindication=contra_text,
                severity=severity,
                notes=notes
            )
            db.insert_contraindication(contra)
            contras_created += 1
    print(f"  Created {contras_created} contraindications\n")
    
    # Final stats
    final_stats = db.get_stats()
    print("=" * 60)
    print("FINAL DATABASE STATISTICS")
    print("=" * 60)
    for table, count in final_stats.items():
        initial = initial_stats.get(table, 0)
        added = count - initial
        print(f"  {table:30s}: {count:4d} (+{added})")
    
    print()
    print("🎉 Sample data created successfully!")
    print()
    print("Next steps:")
    print("  1. Build search indexes:")
    print("     python cli.py index --type all")
    print()
    print("  2. Test repertorization:")
    print("     python cli.py repertorize anxiety insomnia --top 5")
    print()
    print("  3. Search indications:")
    print("     python cli.py search 'nerve pain' --mode hybrid")


if __name__ == "__main__":
    main()

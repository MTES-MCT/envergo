import Engine from 'publicodes';
import { parse } from 'yaml';
import fs from 'fs';


export function evaluateQuality(data) {
  const rules = fs.readFileSync('./dist/hedges/quality.publicodes', 'utf8');
  const parsedRules = parse(rules);
  const engine = new Engine(parsedRules);

    engine.setSituation({
        "Longueur à planter minimum . mixte": data["minimum_lengths_to_plant"]["mixte"],
        "Longueur à planter minimum . alignement": data["minimum_lengths_to_plant"]["alignement"],
        "Longueur à planter minimum . arbustive": data["minimum_lengths_to_plant"]["arbustive"],
        "Longueur à planter minimum . buissonnante": data["minimum_lengths_to_plant"]["buissonnante"],
        "Longueur à planter minimum . dégradée": data["minimum_lengths_to_plant"]["degradee"],
        "Longueur à planter . mixte": data["lengths_to_plant"]["mixte"],
        "Longueur à planter . alignement": data["lengths_to_plant"]["alignement"],
        "Longueur à planter . arbustive": data["lengths_to_plant"]["arbustive"],
        "Longueur à planter . buissonnante": data["lengths_to_plant"]["buissonnante"],
    });
    return {
        isQualitySufficient: engine.evaluate('Qualité globalement suffisante').nodeValue,
        missingPlantation: {
            mixte: engine.evaluate('Manque . mixte').nodeValue,
            alignement: engine.evaluate('Manque . alignement').nodeValue,
            arbustive: engine.evaluate('Manque . arbustive').nodeValue,
            buissonante: engine.evaluate('Manque . buissonnante').nodeValue,
            degradee: engine.evaluate('Manque . dégradée').nodeValue,
        }
    };
}

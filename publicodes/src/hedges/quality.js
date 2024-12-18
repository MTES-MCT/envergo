import Engine from 'publicodes';
import { parse } from 'yaml';
import fs from 'fs';

const rules = fs.readFileSync('./dist/hedges/quality.publicodes', 'utf8');

const parsedRules = parse(rules);

// On initialise un moteur en lui donnant le publicodes sous forme d'objet javascript.
// Ce publicodes va être parsé
const engine = new Engine(parsedRules);


export function evaluateQuality(data) {
    engine.setSituation({
        "Longueur à planter minimum . mixte": data["LPm_5"],
        "Longueur à planter minimum . alignement": data["LPm_4"],
        "Longueur à planter minimum . arbustive": data["LPm_3"],
        "Longueur à planter minimum . buissonnante": data["LPm_2"],
        "Longueur à planter minimum . dégradée": data["LPm_1"],
        "Longueur à planter . mixte": data["LP_5"],
        "Longueur à planter . alignement": data["LP_4"],
        "Longueur à planter . arbustive": data["LP_3"],
        "Longueur à planter . buissonnante": data["LP_2"],
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

const publicodes = require('publicodes');
const fs = require('fs');
const { parse } = require('yaml');


const rules = fs.readFileSync('./rules/hedgesQuality.publicodes', 'utf8');


test('doit indiquer que la qualité de la haie est suffisante', () => {
    const parsedRules = parse(rules);
    const engine = new publicodes.default(parsedRules);
     engine.setSituation({
        "Longueur à planter minimum . mixte": 10,
        "Longueur à planter minimum . alignement": 10,
        "Longueur à planter minimum . arbustive": 10,
        "Longueur à planter minimum . buissonnante": 10,
        "Longueur à planter minimum . dégradée": 10,
        "Longueur à planter . mixte": 20,
        "Longueur à planter . alignement": 0,
        "Longueur à planter . arbustive": 25,
        "Longueur à planter . buissonnante": 5,
    });
    const quality = engine.evaluate('Qualité globalement suffisante').nodeValue;
    expect(quality).toEqual(true);
});


test('doit indiquer que la qualité de la haie est insuffisante', () => {
    const parsedRules = parse(rules);
    const engine = new publicodes.default(parsedRules);
     engine.setSituation({
        "Longueur à planter minimum . mixte": 10,
        "Longueur à planter minimum . alignement": 10,
        "Longueur à planter minimum . arbustive": 10,
        "Longueur à planter minimum . buissonnante": 10,
        "Longueur à planter minimum . dégradée": 10,
        "Longueur à planter . mixte": 5,
        "Longueur à planter . alignement": 5,
        "Longueur à planter . arbustive": 5,
        "Longueur à planter . buissonnante": 5,
    });
    const quality = engine.evaluate('Qualité globalement suffisante').nodeValue;
    expect(quality).toEqual(false);
    const mixte = engine.evaluate('Manque . mixte').nodeValue;
    const alignement = engine.evaluate('Manque . alignement').nodeValue;
    const arbustive = engine.evaluate('Manque . arbustive').nodeValue;
    const buissonante = engine.evaluate('Manque . buissonnante').nodeValue;
    const degradee = engine.evaluate('Manque . dégradée').nodeValue;
    expect(mixte).toEqual(5);
    expect(alignement).toEqual(5);
    expect(arbustive).toEqual(5);
    expect(buissonante).toEqual(5);
    expect(degradee).toEqual(10);

});

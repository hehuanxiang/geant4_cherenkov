//
// DetectorConstruction.cc
//

#include "DetectorConstruction.hh"      // 【用户自定义】头文件，包含类定义
#include "Config.hh"                    // 【配置文件】读取参数

#include "G4RunManager.hh"
#include "G4NistManager.hh"
#include "G4Box.hh"
#include "G4LogicalVolume.hh"
#include "G4PVPlacement.hh"
#include "G4SystemOfUnits.hh"
#include "G4Material.hh"
#include "G4Element.hh"
#include "G4MaterialPropertiesTable.hh"

// DetectorConstruction 继承自 G4VUserDetectorConstruction。
// 当构造 DetectorConstruction 对象时，
// 会先调用父类构造函数构造父类部分，
// 然后初始化子类自己的成员变量（例如 fWaterLogical），
// 最后执行子类构造函数体。
DetectorConstruction::DetectorConstruction()
: G4VUserDetectorConstruction(),
  fWaterLogical(nullptr)
{ }

DetectorConstruction::~DetectorConstruction()
{ }

G4VPhysicalVolume* DetectorConstruction::Construct()
{  
  // Get configuration from JSON config file
  Config* config = Config::GetInstance();
  
  // Get nist material manager
  G4NistManager* nist = G4NistManager::Instance();
  
  // Define elements
  G4double a, z, density;
  G4int nelements;
  
  // Air
  auto N = new G4Element("Nitrogen", "N", z = config->GetNitrogenAtomicNumber(), 
                         a = config->GetNitrogenMass() * g / mole);
  auto O = new G4Element("Oxygen", "O", z = config->GetOxygenAtomicNumber(), 
                         a = config->GetOxygenMass() * g / mole);
  auto air = new G4Material("Air", density = config->GetAirDensity() * mg / cm3, nelements = 2);
  air->AddElement(N, config->GetAirNitrogenFraction() * 100 * perCent);
  air->AddElement(O, config->GetAirOxygenFraction() * 100 * perCent);
  
  // Water
  auto H = new G4Element("Hydrogen", "H", z = config->GetHydrogenAtomicNumber(), 
                         a = config->GetHydrogenMass() * g / mole);
  auto water = new G4Material("Water", density = config->GetWaterDensity() * g / cm3, nelements = 2);
  water->AddElement(H, 2);
  water->AddElement(O, 1);
  
  // Define optical properties for water from config
  std::vector<G4double> photonEnergy = config->GetWaterPhotonEnergies();
  std::vector<G4double> refractiveIndexWater = config->GetWaterRefractiveIndices();
  std::vector<G4double> absorptionWater = config->GetWaterAbsorptionLengths();
  
  // Convert absorption lengths from meters to Geant4 units
  for (auto& val : absorptionWater) {
    val = val * m;
  }
  
  // Convert energies from eV to Geant4 units
  for (auto& val : photonEnergy) {
    val = val * eV;
  }
  
  // MPT(Material Properties Table)
  auto waterMPT = new G4MaterialPropertiesTable();
  waterMPT->AddProperty("RINDEX", photonEnergy, refractiveIndexWater);
  waterMPT->AddProperty("ABSLENGTH", photonEnergy, absorptionWater);
  water->SetMaterialPropertiesTable(waterMPT);
  
  // Define optical properties for air
  std::vector<G4double> airPhotonEnergy = config->GetAirPhotonEnergies();
  for (auto& val : airPhotonEnergy) {
    val = val * eV;
  }
  std::vector<G4double> refractiveIndexAir(airPhotonEnergy.size(), config->GetAirRefractiveIndex());
  auto airMPT = new G4MaterialPropertiesTable();
  airMPT->AddProperty("RINDEX", airPhotonEnergy, refractiveIndexAir);
  air->SetMaterialPropertiesTable(airMPT);

  // Option to switch on/off checking of volumes overlaps
  G4bool checkOverlaps = config->GetCheckOverlaps();

  //     
  // World
  //
  G4double world_sizeX = config->GetWorldSizeX() * cm;
  G4double world_sizeY = config->GetWorldSizeY() * cm;
  G4double world_sizeZ = config->GetWorldSizeZ() * cm;
  
  G4Box* solidWorld =    
    new G4Box("World",                       //its name
       0.5*world_sizeX, 0.5*world_sizeY, 0.5*world_sizeZ);     //its size
      
  G4LogicalVolume* logicWorld =                         
    new G4LogicalVolume(solidWorld,          //its solid
                        air,                 //its material
                        "World");            //its name
  
  // G4PVPlacement 用于将逻辑体积放置在物理空间中，形成物理体积。
  // 这里我们将 World 物理体积放置在原点，没有旋转，母体为 0（表示它是顶层物理体积），并启用重叠检查。
  G4VPhysicalVolume* physWorld = 
    new G4PVPlacement(0,                     //no rotation
                      G4ThreeVector(),       //at (0,0,0)
                      logicWorld,            //its logical volume
                      "World",               //its name
                      0,                     //its mother  volume
                      false,                 //no boolean operation
                      0,                     //copy number
                      checkOverlaps);        //overlaps checking
                       
  // Water Phantom
  // Phase space data has Z in range 17.77-27.35 cm originally
  // But we work in our own coordinate system where water is centered
  G4double water_sizeX = config->GetWaterSizeX() * cm;
  G4double water_sizeY = config->GetWaterSizeY() * cm;
  G4double water_sizeZ = config->GetWaterSizeZ() * cm;
  
  G4Box* solidWater =    
    new G4Box("Water",                    //its name
        0.5*water_sizeX, 0.5*water_sizeY, 0.5*water_sizeZ); //its size
            
  fWaterLogical =                         
    new G4LogicalVolume(solidWater,         //its solid
                        water,              //its material
                        "Water");           //its name
               
  new G4PVPlacement(0,                       //no rotation
                    G4ThreeVector(config->GetWaterPositionX() * cm, 
                                  config->GetWaterPositionY() * cm,
                                  config->GetWaterPositionZ() * cm),  //position from config
                    fWaterLogical,           //its logical volume
                    "Water",                 //its name
                    logicWorld,              //its mother  volume
                    false,                   //no boolean operation
                    0,                       //copy number
                    checkOverlaps);          //overlaps checking

  //
  //always return the physical World
  //
  return physWorld;
}

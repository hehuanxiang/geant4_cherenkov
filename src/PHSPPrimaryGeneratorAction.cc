//
// PHSPPrimaryGeneratorAction.cc
//

#include "PHSPPrimaryGeneratorAction.hh"

#include "G4Event.hh"
#include "G4ParticleTable.hh"
#include "G4ParticleDefinition.hh"
#include "G4SystemOfUnits.hh"
#include "G4ThreeVector.hh"
#include "G4UnitsTable.hh"
#include "Randomize.hh"
#include "G4Threading.hh"
#include <iostream>
#include <sstream>
#include <algorithm>
#include <cstring>
#include <thread>
#include <chrono>
#include "G4UIcommand.hh"

// Define static members (one copy shared by all threads)
std::vector<PHSPParticle> PHSPPrimaryGeneratorAction::fGlobalPHSPData;
G4bool PHSPPrimaryGeneratorAction::fDataLoaded = false;
#ifdef G4MULTITHREADED
G4Mutex PHSPPrimaryGeneratorAction::fLoadMutex = G4MUTEX_INITIALIZER;
#endif

PHSPPrimaryGeneratorAction::PHSPPrimaryGeneratorAction(const G4String& phspFilePath)
: G4VUserPrimaryGeneratorAction(),
  fCurrentParticleIndex(0),
  fCycleData(false),              // 是否循环使用PHSP数据，默认为false
  fParticleGun(nullptr)
{
  G4int n_particle = 1;
  fParticleGun = new G4ParticleGun(n_particle);

  // Load PHSP data (only once, protected by mutex)
  LoadGlobalPHSPData(phspFilePath);
  
  // Set local reference to global data
  fPHSPData = fGlobalPHSPData;
  
  // Only print statistics on master thread to avoid clutter
  if (G4Threading::IsMasterThread()) {
    PrintStatistics();
  }
}

PHSPPrimaryGeneratorAction::~PHSPPrimaryGeneratorAction()
{
  delete fParticleGun;
}

void PHSPPrimaryGeneratorAction::ReadPHSPFile(const G4String& filePath)
{
  std::ifstream infile(filePath);
  
  if (!infile.is_open()) {
    G4cerr << "ERROR: Cannot open PHSP file: " << filePath << G4endl;
    return;
  }

  G4String line;
  G4int lineNumber = 0;
  
  while (std::getline(infile, line)) {
    lineNumber++;
    
    if (line.empty() || line[0] == '#') {
      continue;
    }

    std::istringstream iss(line);
    PHSPParticle particle;
    
    G4int particleType;
    G4double weight = 1.0;
    
    if (iss >> particle.posX >> particle.posY >> particle.posZ
           >> particle.dirX >> particle.dirY >> particle.dirZ
           >> particle.energy >> particleType) {
      
      particle.particleType = particleType;
      
      if (!(iss >> weight)) {
        weight = 1.0;
      }
      particle.weight = weight;
      
      fPHSPData.push_back(particle);
      
    } else {
      if (lineNumber <= 5) {  // 只在前几行报错
        G4cerr << "Warning: Error parsing line " << lineNumber << G4endl;
      }
    }
  }
  
  infile.close();
  G4cout << "ASCII PHSP: Loaded " << fPHSPData.size() << " particles" << G4endl;
}

G4ParticleDefinition* PHSPPrimaryGeneratorAction::GetParticleByCode(G4int code)
{
  G4ParticleTable* particleTable = G4ParticleTable::GetParticleTable();
  
  switch (code) {
    case 11:    return particleTable->FindParticle("e-");
    case -11:   return particleTable->FindParticle("e+");
    case 22:    return particleTable->FindParticle("gamma");
    case 211:   return particleTable->FindParticle("pi+");
    case -211:  return particleTable->FindParticle("pi-");
    default:
      return particleTable->FindParticle("e-");
  }
}

void PHSPPrimaryGeneratorAction::GeneratePrimaries(G4Event* anEvent)
{
  if (fPHSPData.empty()) {
    G4cerr << "ERROR: No PHSP data loaded!" << G4endl;
    return;
  }

  PHSPParticle& particle = fPHSPData[fCurrentParticleIndex];
  
  G4ParticleDefinition* particleDef = GetParticleByCode(particle.particleType);
  fParticleGun->SetParticleDefinition(particleDef);
  
  // PHSP coordinates are in cm, convert to Geant4 units
  G4ThreeVector position(particle.posX * cm, particle.posY * cm, particle.posZ * cm);
  fParticleGun->SetParticlePosition(position);
  
  G4ThreeVector direction(particle.dirX, particle.dirY, particle.dirZ);
  if (direction.mag() > 0) {
    direction = direction.unit();
  }
  fParticleGun->SetParticleMomentumDirection(direction);
  
  fParticleGun->SetParticleEnergy(particle.energy * MeV);
  
  fParticleGun->GeneratePrimaryVertex(anEvent);
  
  fCurrentParticleIndex++;
  
  if (fCurrentParticleIndex >= (G4int)fPHSPData.size()) {
    if (fCycleData) {
      fCurrentParticleIndex = 0;
    }
  }
}

void PHSPPrimaryGeneratorAction::PrintStatistics()
{
  G4cout << G4endl;
  G4cout << "========== PHSP Statistics ==========" << G4endl;
  G4cout << "Total particles in PHSP: " << fPHSPData.size() << G4endl;
  
  if (fPHSPData.empty()) {
    return;
  }
  
  std::map<G4int, G4int> typeCount;
  G4double minEnergy = 1e10, maxEnergy = 0;
  
  for (const auto& p : fPHSPData) {
    typeCount[p.particleType]++;
    minEnergy = std::min(minEnergy, p.energy);
    maxEnergy = std::max(maxEnergy, p.energy);
  }
  
  G4cout << "Particle types:" << G4endl;
  for (const auto& pair : typeCount) {
    G4String particleName;
    if (pair.first == 11) particleName = "e-";
    else if (pair.first == -11) particleName = "e+";
    else if (pair.first == 22) particleName = "gamma";
    else particleName = G4UIcommand::ConvertToString(pair.first);
    
    G4cout << "  " << particleName << ": " << pair.second << G4endl;
  }
  
  G4cout << "Energy range: " << minEnergy << " - " << maxEnergy << " MeV" << G4endl;
  G4cout << "====================================" << G4endl << G4endl;
}
void PHSPPrimaryGeneratorAction::ReadIAEAPHSPFile(const G4String& filePath, const G4String& headerPath)
{
  std::ifstream infile(filePath, std::ios::binary);
  
  if (!infile.is_open()) {
    G4cerr << "ERROR: Cannot open IAEA PHSP file: " << filePath << G4endl;
    return;
  }

  G4cout << "Reading IAEA binary PHSP file (25 bytes per record)..." << G4endl;
  G4cout << "Format: [ParticleType(1B)] [Energy(4B)] [X,Y,Z,U,V(5*4B)]" << G4endl;
  
  // IAEA Limited Format with 25 bytes per record:
  // 1 signed byte for particle type (sign indicates if W is negative)
  // 6 floats (E, X, Y, Z, U, V) = 24 bytes
  // W is calculated from: W = ±sqrt(1 - U² - V²)
  // Total = 1 + 24 = 25 bytes
  
  int particleCount = 0;
  
  while (true) {
    PHSPParticle particle;
    
    // Read particle type byte (signed char)
    char type_byte;
    infile.read(&type_byte, 1);
    if (!infile) break;
    
    // Sign of type byte indicates if W (cos Z) is negative
    G4bool cosZIsNegative = (type_byte < 0);
    G4int particleTypeCode = std::abs((int)type_byte);
    
    // Read energy and position/direction
    float energy, x, y, z, u, v;
    infile.read(reinterpret_cast<char*>(&energy), sizeof(float));
    infile.read(reinterpret_cast<char*>(&x), sizeof(float));
    infile.read(reinterpret_cast<char*>(&y), sizeof(float));
    infile.read(reinterpret_cast<char*>(&z), sizeof(float));
    infile.read(reinterpret_cast<char*>(&u), sizeof(float));
    infile.read(reinterpret_cast<char*>(&v), sizeof(float));
    
    // Calculate W from direction cosines: W = ±sqrt(1 - U² - V²)
    G4double cosZSquared = 1.0 - u*u - v*v;
    G4double w = 0.0;
    if (cosZSquared >= 0.0) {
      w = std::sqrt(cosZSquared);
    }
    if (cosZIsNegative) {
      w = -w;
    }
    
    particle.posX = x;
    particle.posY = y;
    particle.posZ = z;
    particle.dirX = u;
    particle.dirY = v;
    particle.dirZ = w;
    particle.energy = energy;  // Use actual energy from PHSP file
    particle.weight = 1.0;     // Constant weight
    
    // Map particle type code to Geant4 PDG codes
    if (particleTypeCode == 1)
      particle.particleType = 22;  // photon
    else if (particleTypeCode == 2)
      particle.particleType = 11;  // electron
    else if (particleTypeCode == 3)
      particle.particleType = -11; // positron
    else
      particle.particleType = 22;  // default to photon
    
    fPHSPData.push_back(particle);
    particleCount++;
  }

  infile.close();

  G4cout << "IAEA PHSP: Loaded " << particleCount << " particles from file" << G4endl;
}

void PHSPPrimaryGeneratorAction::LoadGlobalPHSPData(const G4String& phspFilePath)
{
  // Thread-safe load: only load once, even if multiple threads try to load
#ifdef G4MULTITHREADED
  G4AutoLock lock(&fLoadMutex);
#endif
  
  // Double-check pattern to avoid redundant loading
  if (fDataLoaded) {
    return;
  }
  
  // 检查是否有配套的header文件（IAEA二进制格式）
  G4String headerPath = phspFilePath;
  headerPath.erase(headerPath.find_last_of('.'));
  headerPath += ".header";
  
  G4cout << "Master thread loading PHSP data..." << G4endl;
  G4cout << "Looking for header file: " << headerPath << G4endl;
  
  std::ifstream headerFile(headerPath);
  if (headerFile.good()) {
    headerFile.close();
    G4cout << "Detected IAEA PHSP format (binary with header file)" << G4endl;
    ReadIAEAPHSPFile(phspFilePath, headerPath);
  } else {
    G4cout << "Detected ASCII PHSP format" << G4endl;
    ReadPHSPFile(phspFilePath);
  }
  
  // Move local data to global container
  fGlobalPHSPData = fPHSPData;
  fDataLoaded = true;
  
  G4cout << "Global PHSP data loaded: " << fGlobalPHSPData.size() << " particles" << G4endl;
}